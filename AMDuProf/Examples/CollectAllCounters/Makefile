all: CollectAllCounters

CollectAllCounters: CollectAllCounters.cpp
	g++ -O -std=c++11 CollectAllCounters.cpp -I ../../include/ -l AMDPowerProfileAPI -L ../../bin -Wl,-rpath ../../bin/  -o CollectAllCounters
clean:
	rm -rf *.o CollectAllCounters

