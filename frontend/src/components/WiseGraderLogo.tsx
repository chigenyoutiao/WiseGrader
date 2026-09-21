interface WiseGraderLogoProps {
  size?: number;
  className?: string;
}

export default function WiseGraderLogo({ size = 32, className = '' }: WiseGraderLogoProps) {
  return (
    <img
      src="/logo.png"
      alt="WiseGrader Logo"
      className={`rounded-xl object-contain ${className}`}
      style={{
        width: size,
        height: size,
      }}
    />
  );
}

