interface BrandLogoProps {
  height?: number;
  maxWidth?: number | string;
}

export function BrandLogo({ height = 32, maxWidth = 156 }: BrandLogoProps) {
  return (
    <img
      src="/logo.png"
      alt="Джейсан"
      style={{
        display: 'block',
        height,
        maxWidth,
        width: 'auto',
        objectFit: 'contain',
      }}
    />
  );
}
