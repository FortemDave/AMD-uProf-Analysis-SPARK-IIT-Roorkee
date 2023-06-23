CC=clang
CFLAGS+=-std=c11 -g -Wall
OMP_FLAGS=-fopenmp
OUTDIR=./bin
TIME=time
MD=mkdir -p
RD=rm -rf

all: out-dir collatz-seq-serial collatz-seq-omp collatz-seq-omp-dyn collatz-seq-omp-dyn20

out-dir:
	$(MD) $(OUTDIR)

collatz-seq-serial: collatz-sequence-omp.c
	$(CC) $(CFLAGS) $< -o $(OUTDIR)/$@

collatz-seq-omp: collatz-sequence-omp.c
	$(CC) $(CFLAGS) $(OMP_FLAGS) $< -o $(OUTDIR)/$@

collatz-seq-omp-dyn: collatz-sequence-omp-dyn.c
	$(CC) $(CFLAGS) $(OMP_FLAGS) $< -o $(OUTDIR)/$@

collatz-seq-omp-dyn20: collatz-sequence-omp-dyn20.c
	$(CC) $(CFLAGS) $(OMP_FLAGS) $< -o $(OUTDIR)/$@

clean:
	$(RD) $(OUTDIR)

run: all
	$(TIME) $(OUTDIR)/collatz-seq-serial
	$(TIME) $(OUTDIR)/collatz-seq-omp
	$(TIME) $(OUTDIR)/collatz-seq-omp-dyn
	$(TIME) $(OUTDIR)/collatz-seq-omp-dyn20
