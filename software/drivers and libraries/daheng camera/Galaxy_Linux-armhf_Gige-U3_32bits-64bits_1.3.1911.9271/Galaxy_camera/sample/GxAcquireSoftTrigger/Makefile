# Makefile for sample program
.PHONY			: all clean

# the program to build
NAME			:= GxAcquireSoftTrigger

# Build tools and flags
CXX			:= g++
LD			:= g++
SRCS                    := $(wildcard *.cpp)
OBJS                    := $(patsubst %cpp, %o, $(SRCS))
CPPFLAGS		:= -w -I./

LDFLAGS			:=-lgxiapi -lpthread 

all			: $(NAME)

$(NAME)			: $(OBJS)
	$(LD) -o $@ $^ $(CPPFLAGS) $(LDFLAGS)

%.o		: %.cpp
	$(CXX) $(CPPFLAGS) -c -o $@ $<

clean			:
	$(RM) *.o $(NAME)

