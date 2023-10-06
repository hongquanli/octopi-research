# M2U-Net PyTorch model
# 
# MIT License

# Copyright (c) September 2018 Tim Laibacher

# Modified April 2023 Kevin Marx

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Encoder part adopted from MobileNetv2 class by @tonylins Ji Lin under Apache License 2.0
# https://github.com/tonylins/pytorch-mobilenet-v2/

import torch
import torch.nn as nn
import math
import os

def conv_bn(inp, oup, stride):
    return nn.Sequential(
        nn.Conv2d(inp, oup, 3, stride, 1, bias=False),
        nn.BatchNorm2d(oup),
        nn.ReLU6(inplace=True)
    )


def conv_1x1_bn(inp, oup):
    return nn.Sequential(
        nn.Conv2d(inp, oup, 1, 1, 0, bias=False),
        nn.BatchNorm2d(oup),
        nn.ReLU6(inplace=True)
    )

class InvertedResidual(nn.Module):
    def __init__(self, inp, oup, stride, expand_ratio):
        super(InvertedResidual, self).__init__()
        self.stride = stride
        assert stride in [1, 2]

        hidden_dim = round(inp * expand_ratio)
        self.use_res_connect = self.stride == 1 and inp == oup

        if expand_ratio == 1:
            # depthwise separable convolution block
            self.conv = nn.Sequential(
                # dw
                nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # pw-linear
                nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup),
            )
        else:
            # Bottleneck with expansion layer
            self.conv = nn.Sequential(
                # pw
                nn.Conv2d(inp, hidden_dim, 1, 1, 0, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # dw
                nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # pw-linear
                nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup),
            )

    def forward(self, x):
        if self.use_res_connect:
            return x + self.conv(x)
        else:
            return self.conv(x)
        
class Encoder(nn.Module):
    """
    14 layers of MobileNetv2 as encoder part
    """
    def __init__(self, input_channels=3):
        super(Encoder, self).__init__()
        block = InvertedResidual
        interverted_residual_setting = [
            # t, c, n, s
            [1, 16, 1, 1],
            [6, 24, 2, 2],
            [6, 32, 3, 2],
            [6, 64, 4, 2],
            [6, 96, 3, 1],
        ]
        # Encoder Part
        input_channel = 32 # number of input channels to first inverted (residual) block
        self.layers = [conv_bn(input_channels, 32, 2)]
        # building inverted residual blocks
        for t, c, n, s in interverted_residual_setting:
            output_channel = c
            for i in range(n):
                if i == 0:
                    self.layers.append(block(input_channel, output_channel, s, expand_ratio=t))
                else:
                    self.layers.append(block(input_channel, output_channel, 1, expand_ratio=t))
                input_channel = output_channel
        # make it nn.Sequential
        self.layers = nn.Sequential(*self.layers)
                
class DecoderBlock(nn.Module):
    """
    Decoder block: upsample and concatenate with features maps from the encoder part
    """
    def __init__(self,up_in_c,x_in_c,upsamplemode='bilinear',expand_ratio=0.15):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2,mode=upsamplemode,align_corners=False) # H, W -> 2H, 2W
        self.ir1 = InvertedResidual(up_in_c+x_in_c,(x_in_c + up_in_c) // 2,stride=1,expand_ratio=expand_ratio)

    def forward(self,up_in,x_in):
        up_out = self.upsample(up_in)
        cat_x = torch.cat([up_out, x_in] , dim=1)
        x = self.ir1(cat_x)
        return x
    
class LastDecoderBlock(nn.Module):
    def __init__(self,x_in_c,upsamplemode='bilinear',expand_ratio=0.15, output_channels=1, activation='linear'):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2,mode=upsamplemode,align_corners=False) # H, W -> 2H, 2W
        self.ir1 = InvertedResidual(x_in_c,16,stride=1,expand_ratio=expand_ratio)
        layers =  [
            nn.Conv2d(16, output_channels, 1, 1, 0, bias=True),
        ]
        if activation == 'sigmoid':
            layers.append(nn.Sigmoid())
        elif activation == 'softmax':
            layers.append(nn.Softmax(dim=1))
        elif activation == 'linear' or activation is None:
            pass
        else:
            raise NotImplementedError('Activation {} not implemented'.format(activation))
        self.conv = nn.Sequential(
           *layers
        )

    def forward(self,up_in,x_in):
        up_out = self.upsample(up_in)
        cat_x = torch.cat([up_out, x_in] , dim=1)
        x = self.ir1(cat_x)
        x = self.conv(x)
        return x
    
class M2UNet(nn.Module):
    def __init__(self,encoder,upsamplemode='bilinear',output_channels=1, activation="linear", expand_ratio=0.15, input_channels=3):
        super(M2UNet,self).__init__()
        encoder = list(encoder.children())[0]
        # Encoder
        self.conv1 = encoder[0:2]
        self.conv2 = encoder[2:4]
        self.conv3 = encoder[4:7]
        self.conv4 = encoder[7:14]
        # Decoder
        self.decode4 = DecoderBlock(96,32,upsamplemode,expand_ratio)
        self.decode3 = DecoderBlock(64,24,upsamplemode,expand_ratio)
        self.decode2 = DecoderBlock(44,16,upsamplemode,expand_ratio)
        self.decode1 = LastDecoderBlock((30+input_channels),upsamplemode,expand_ratio, output_channels=output_channels, activation=activation)
        # initilaize weights 
        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
                if m.bias is not None:
                    m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.Linear):
                n = m.weight.size(1)
                m.weight.data.normal_(0, 0.01)
                m.bias.data.zero_()
        
    def forward(self,x):
        conv1 = self.conv1(x)
        conv2 = self.conv2(conv1)
        conv3 = self.conv3(conv2)
        conv4 = self.conv4(conv3)
        decode4 = self.decode4(conv4,conv3)
        decode3 = self.decode3(decode4,conv2)
        decode2 = self.decode2(decode3,conv1)
        decode1 = self.decode1(decode2,x)
        return decode1
        
def m2unet(upsamplemode='bilinear',expand_ratio=0.15, output_channels=1, activation="linear", input_channels=3):
    enc = Encoder(input_channels=input_channels)
    model = M2UNet(enc, upsamplemode=upsamplemode,expand_ratio=expand_ratio, output_channels=output_channels, activation=activation, input_channels=input_channels)   
    return model