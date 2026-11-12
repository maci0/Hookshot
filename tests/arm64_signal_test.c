#include <windows.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>

static volatile unsigned char *page;
static int faults;

static LONG on_fault(EXCEPTION_POINTERS *e) {
    if (e->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION ||
        e->ExceptionRecord->ExceptionInformation[1] != (ULONG_PTR)page ||
        e->ExceptionRecord->ExceptionInformation[0] != (ULONG_PTR)faults || faults > 1)
        return EXCEPTION_CONTINUE_SEARCH;
    int protection = faults++ ? PROT_READ | PROT_WRITE : PROT_READ;
    if (mprotect((void *)page, (size_t)sysconf(_SC_PAGESIZE), protection))
        return EXCEPTION_CONTINUE_SEARCH;
    return EXCEPTION_CONTINUE_EXECUTION;
}

int main(void) {
    size_t size = (size_t)sysconf(_SC_PAGESIZE);
    page = mmap(NULL, size, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (page == MAP_FAILED || !AddVectoredExceptionHandler(1, on_fault)) return 1;
    volatile unsigned char value = *page;
    *page = value + 1;
    if (faults != 2 || *page != 1) return 2;
    puts("ARM64 read and write fault classification passed");
    return 0;
}
