import { Grid } from 'antd';

type Breakpoint = 'md' | 'lg';

export function useIsMobileLayout(breakpoint: Breakpoint = 'md'): boolean {
  const screens = Grid.useBreakpoint();

  if (breakpoint === 'lg') {
    return !screens.lg;
  }

  return !screens.md;
}
