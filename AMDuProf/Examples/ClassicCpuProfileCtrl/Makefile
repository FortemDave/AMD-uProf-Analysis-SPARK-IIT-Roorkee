#######################################
# Use the default tools, not aliases
# and other stuff
#######################################
LS				:= /bin/ls
RM				:= /bin/rm
LN				:= /bin/ln
CP				:= /bin/cp
MKDIR			:= /bin/mkdir

#######################################
# ClassicCpuProfileCtrl
#######################################

AMDTCMM_EXE		:=  ClassicCpuProfileCtrl
AMDUPROF_INC    :=  ../../include/
AMDUPROF_LIB    :=  ../../lib/x64/

.PHONY: all clean

all: ClassicCpuProfileCtrl
ClassicCpuProfileCtrl: ClassicCpuProfileCtrl.cpp
	g++ -std=c++11 ClassicCpuProfileCtrl.cpp -I$(AMDUPROF_INC) -L$(AMDUPROF_LIB) -lAMDProfileController -lrt -pthread -o $(AMDTCMM_EXE)

clean:
	$(RM) -f $(AMDTCMM_EXE)
