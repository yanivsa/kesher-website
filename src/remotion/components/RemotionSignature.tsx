import React from "react";
import {
  Easing,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

export interface RemotionSignatureProps {
  startFrame?: number;
  durationInFrames?: number;
  color?: string;
  width?: number | string;
  height?: number | string;
  maskSrc?: string;
  style?: React.CSSProperties;
  className?: string;
}

export const RemotionSignature: React.FC<RemotionSignatureProps> = ({
  startFrame = 0,
  durationInFrames = 45,
  color = "#e6af2e",
  width = 300,
  height,
  maskSrc = "signature-mask.svg",
  style,
  className,
}) => {
  const frame = useCurrentFrame();
  const current = frame - startFrame;

  // Animate once and clamp to final state (100% visible)
  const clipProgress = interpolate(current, [0, durationInFrames], [100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.22, 0.61, 0.36, 1),
  });

  const opacity = interpolate(current, [0, Math.max(1, durationInFrames * 0.2)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const maskUrl = staticFile(maskSrc);

  return (
    <div
      className={className}
      style={{
        width,
        height,
        aspectRatio: "1196 / 385",
        background: color,
        WebkitMask: `url(${maskUrl}) center / contain no-repeat`,
        mask: `url(${maskUrl}) center / contain no-repeat`,
        clipPath: `inset(0 0 0 ${clipProgress}%)`,
        opacity: current < 0 ? 0 : opacity,
        display: "block",
        flexShrink: 0,
        ...style,
      }}
      aria-label="חתימתה של שירה סהרוני"
    />
  );
};
