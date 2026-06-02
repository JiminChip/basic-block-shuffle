#include <stdio.h>

__attribute__((noinline)) static int branchy(int x) {
  int acc = 0;

  for (int i = 0; i < 32; ++i) {
    if ((x + i) & 1)
      acc += i * 3;
    else
      acc -= i;

    if ((acc ^ x) & 4)
      acc ^= (i << 1);
    else
      acc += x & 7;
  }

  if (acc == 31337)
    return acc - x;
  if (acc & 8)
    return acc + 11;
  return acc - 5;
}

int main(int argc, char **argv) {
  int x = argc;
  for (char **p = argv; *p; ++p)
    x += (int)(*p)[0];

  printf("%d\n", branchy(x));
  return 0;
}
