# Makefile for sample program
.PHONY                  : all clean

# the program to build
NAME                    := HalconQRCode

# Build tools and flags
CXX                     := g++
LD                      := g++
SRCS                    := $(wildcard *.cpp)
OBJS                    := $(patsubst %cpp, %o, $(SRCS))

CPPFLAGS   = -I$(HALCONROOT)/include/halconcpp \
      -I$(HALCONROOT)/include \
      -L/usr/lib -L./ \
      -Wl,-rpath=/usr/lib:./

LDFLAGS   := -lgxiapi -lpthread -ldl \
	     -L$(HALCONROOT)/lib/$(HALCONARCH) -lhalconcpp -lhalcon

all                     : $(NAME)

$(NAME)                 : $(OBJS)
	$(LD) -o $@ $^ -Wl,-rpath,$(HALCONROOT)/lib/$(HALCONARCH)  $(CPPFLAGS) $(LDFLAGS)

$(NAME).o               : $(NAME).cpp
	$(CXX) $(CPPFLAGS) -c -o $@ $<

clean                   :
	$(RM) $(OBJS) $(NAME)
