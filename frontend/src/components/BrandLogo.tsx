interface BrandLogoProps {
  height?: number;
  maxWidth?: number | string;
  variant?: 'auto' | 'dark' | 'light';
}

export function BrandLogo({ height = 32, maxWidth = 156, variant = 'auto' }: BrandLogoProps) {
  const src =
    variant === 'dark'
      ? '/logo.png'
      : variant === 'light'
        ? '/logo-light.png'
        : undefined;

  return (
    <picture>
      {variant === 'auto' ? <source srcSet="/logo.png" media="(prefers-color-scheme: dark)" /> : null}
      <img
        src={src ?? '/logo-light.png'}
        alt="Джейсан"
        style={{
          display: 'block',
          height,
          maxWidth,
          width: 'auto',
          objectFit: 'contain',
        }}
      />
    </picture>
  );
}
