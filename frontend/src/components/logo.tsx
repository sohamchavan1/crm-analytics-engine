"use client";

import Image from "next/image";

export function Logo({ className = "", height = 20 }: { className?: string; height?: number }) {
  return (
    <Image
      src="/logo.png"
      alt="Attributics"
      width={Math.round(height * 8.5)}
      height={height}
      className={className}
      priority
    />
  );
}

export function LogoFull({ className = "" }: { className?: string }) {
  return (
    <div className={className}>
      <Image
        src="/logo.png"
        alt="Attributics"
        width={170}
        height={20}
        className="h-5 w-auto"
        priority
      />
    </div>
  );
}
