/* feasible.c — C kernel for one (n, M) feasibility question:
 * does an n-element sum-distinct set of positive integers with largest element
 * EXACTLY M exist?
 *
 * Exact mirror of arms/exhaustive.py:feasible_with_max (same DFS order, same
 * conservative prunes P1–P4, same non-circular A_VERIFIED table) — the Python arm
 * remains the reference implementation; this kernel exists because the n>=9 gate
 * runs are compute-bound. The Python driver (exhaustive.py --engine c) shells out
 * per M, so ledgers/floors/JSON receipts stay uniform.
 *
 * Bitset semantics: bit s set <=> some subset of chosen elements sums to s.
 * Adding element e is collision-free iff ((sums << e) & sums) == 0.
 *
 * Usage:   ./feasible <n> <M> <budget_seconds>
 * Stdout:  "witness <e1> <e2> ... <en>"  (exit 0)  — sum-distinct set found
 *          "infeasible <nodes>"          (exit 1)  — exhausted, no set
 *          "budget <nodes>"              (exit 2)  — deadline hit, NO negative claim
 * Build:   gcc -O2 -o arms/feasible arms/feasible.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define MAXN 24
#define MAXWORDS 4096  /* supports total sums up to ~262k: n=15 records territory */

/* OWN-REPRODUCED exact optima (VR-3 + gate VRs). Keep in sync with
 * exhaustive.py:A_VERIFIED — the Python driver cross-checks this table at startup. */
static const int A_VERIFIED[] = {0, 1, 2, 4, 7, 13, 24, 44, 84, 161};
static const int A_VERIFIED_MAX = 9;

static int n_target, words;
static int top_stride = 1, top_offset = 0;  /* P7 M1: depth-1 subtree partition */
static long need;               /* 2^n - 1: minimal total sum (P3) */
static long need_sq;            /* (4^n - 1)/3: minimal sum of squares (P5, variance) */
static uint64_t nodes = 0;
static double deadline;
static int chosen[MAXN];

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

static long binom(int a, int b) {
    if (b < 0 || b > a) return 0;
    long r = 1;
    for (int i = 1; i <= b; i++) r = r * (a - b + i) / i;
    return r;
}

static long subset_floor(int k) {
    if (k <= 0) return 0;
    if (k <= A_VERIFIED_MAX) return A_VERIFIED[k];
    return binom(k, k / 2);
}

/* overlap test: ((sums << e) & sums) != 0, without materializing the shift.
 * live = highest word index holding set bits (bits occupy [0, partial]), so loops
 * skip the dead top of the buffer — pure speed; traversal order and node counts
 * unchanged (the mirror invariant vs exhaustive.py still binds and is re-checked). */
static int collides(const uint64_t *sums, int e, int live) {
    int ws = e >> 6, bs = e & 63;
    int top = live + ws + 1;
    if (top > words - 1) top = words - 1;
    for (int i = top; i >= ws; i--) {
        int j = i - ws;
        if (j > live) continue;
        uint64_t sh = sums[j] << bs;
        if (bs && j - 1 >= 0) sh |= sums[j - 1] >> (64 - bs);
        if (sh & sums[i]) return 1;
    }
    return 0;
}

/* child = sums | (sums << e); child[0..top] fully written, [top+1..) zeroed */
static void add_elem(const uint64_t *sums, uint64_t *child, int e, int live) {
    int ws = e >> 6, bs = e & 63;
    int top = live + ws + 1;
    if (top > words - 1) top = words - 1;
    for (int i = top; i >= 0; i--) {
        uint64_t sh = 0;
        int j = i - ws;
        if (j >= 0 && j <= live) {
            sh = sums[j] << bs;
            if (bs && j - 1 >= 0) sh |= sums[j - 1] >> (64 - bs);
        }
        child[i] = sums[i] | sh;
    }
    if (top < words - 1)
        memset(child + top + 1, 0, (size_t)(words - 1 - top) * 8);
}

static long max_sq(int k, int cap) {
    /* largest achievable sum of squares of k distinct elements <= cap */
    long s = 0;
    for (int i = 0; i < k; i++) { long v = cap - i; s += v * v; }
    return s;
}

/* returns 1 witness / 0 infeasible-exhausted / -1 budget */
static int dfs(int k, int cap, const uint64_t *sums, long partial, long partial_sq,
               int depth) {
    if (k == 0) return 1;
    if ((++nodes & 0xFFFFF) == 0 && now() > deadline) return -1;
    if (cap < k) return 0;                                        /* P1 */
    long fl = subset_floor(k);
    if (cap < fl) return 0;                                       /* P4 */
    if (partial + (long)k * cap - (long)k * (k - 1) / 2 < need)   /* P3 */
        return 0;
    if (partial_sq + max_sq(k, cap) < need_sq)                    /* P5 */
        return 0;
    if (k < 62 && (1L << k) > (long)k * cap + 1) return 0;        /* P2 */
    uint64_t child[MAXWORDS];
    int live = (int)(partial >> 6) + 1;   /* words holding bits [0, partial] */
    for (int e = cap; e >= fl; e--) {
        /* P7 M1: partition the depth-1 element choices across workers; every deeper
         * node belongs to exactly one worker, so the workers' node-count sum equals
         * the single-process count + (K-1) root increments (asserted by tests). */
        if (depth == 1 && ((cap - e) % top_stride) != top_offset)
            continue;
        if (!collides(sums, e, live)) {
            add_elem(sums, child, e, live);
            chosen[depth] = e;
            int r = dfs(k - 1, e - 1, child, partial + e, partial_sq + (long)e * e,
                        depth + 1);
            if (r) return r;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--table") == 0) {   /* driver sync check */
        for (int k = 1; k <= A_VERIFIED_MAX; k++) printf("%d ", A_VERIFIED[k]);
        printf("\n");
        return 0;
    }
    if (argc < 4) { fprintf(stderr, "usage: feasible <n> <M> <budget_s>\n"); return 3; }
    n_target = atoi(argv[1]);
    int M = atoi(argv[2]);
    deadline = now() + atof(argv[3]);
    if (argc >= 6) { top_stride = atoi(argv[4]); top_offset = atoi(argv[5]); }
    if (top_stride < 1 || top_offset < 0 || top_offset >= top_stride) {
        fprintf(stderr, "bad stride/offset\n"); return 3;
    }
    if (n_target < 1 || n_target > MAXN) { fprintf(stderr, "n out of range\n"); return 3; }
    long total_bits = (long)n_target * M + 2;
    words = (int)(total_bits / 64 + 2);
    if (words > MAXWORDS) { fprintf(stderr, "bitset too large\n"); return 3; }
    need = (1L << n_target) - 1;
    need_sq = ((1L << (2 * n_target)) - 1) / 3;

    static uint64_t sums[MAXWORDS];
    memset(sums, 0, sizeof(uint64_t) * words);
    sums[0] = 1;                          /* {} */
    sums[M >> 6] |= 1ULL << (M & 63);     /* {M} */
    chosen[0] = M;

    int r = dfs(n_target - 1, M - 1, sums, M, (long)M * M, 1);
    if (r == 1) {
        printf("witness %llu", (unsigned long long)nodes);
        for (int i = 0; i < n_target; i++) printf(" %d", chosen[i]);
        printf("\n");
        return 0;
    }
    if (r == 0) { printf("infeasible %llu\n", (unsigned long long)nodes); return 1; }
    printf("budget %llu\n", (unsigned long long)nodes);
    return 2;
}
