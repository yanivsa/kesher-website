import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { RemotionSignature } from "./RemotionSignature";

export interface FullScreenSignatureOutroProps {
  durationSeconds?: number;
  backgroundColor?: string;
  signatureColor?: string;
  signatureImageSrc?: string;
  title?: string;
  subtitle?: string;
  websiteUrl?: string;
  zIndex?: number;
}

export const FullScreenSignatureOutro: React.FC<FullScreenSignatureOutroProps> = ({
  durationSeconds = 2,
  backgroundColor = "linear-gradient(135deg, #18281f 0%, #0d1712 100%)",
  signatureColor = "#f4d068",
  signatureImageSrc = "signature-mask.svg",
  title = "שירה סהרוני",
  subtitle = "ייעוץ זוגי, הנחיית הורים וגישור",
  websiteUrl = "kesher.saharoni.com",
  zIndex = 9999,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width } = useVideoConfig();

  const outroLengthFrames = Math.round(durationSeconds * fps);
  const startFrame = Math.max(0, durationInFrames - outroLengthFrames);

  // If before outro start, do not render or keep opacity 0
  if (frame < startFrame) {
    return null;
  }

  const current = frame - startFrame;

  // Rapid fade-in transition into the outro card
  const backdropOpacity = interpolate(current, [0, Math.min(10, outroLengthFrames * 0.2)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cardScale = spring({
    frame: current,
    fps,
    config: { damping: 14, stiffness: 90 },
  });

  // Calculate signature width based on composition orientation
  const isVertical = width < 1200;
  const signatureWidth = isVertical ? "75%" : "480px";

  return (
    <AbsoluteFill
      style={{
        zIndex,
        background: backgroundColor,
        opacity: backdropOpacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "60px 40px",
        direction: "rtl",
        fontFamily: "'Heebo', 'Rubik', Arial, sans-serif",
      }}
    >
      {/* Subtle brand glow circle */}
      <div
        style={{
          position: "absolute",
          width: isVertical ? "600px" : "450px",
          height: isVertical ? "600px" : "450px",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(230, 175, 46, 0.18) 0%, rgba(230, 175, 46, 0) 70%)",
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          transform: `scale(${cardScale})`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: isVertical ? "32px" : "20px",
          maxWidth: isVertical ? "90%" : "800px",
          zIndex: 2,
        }}
      >
        {/* Animated Signature - runs once in the first 35-40 frames of outro, then stays locked */}
        <RemotionSignature
          startFrame={startFrame + 5}
          durationInFrames={Math.min(38, outroLengthFrames - 10)}
          color={signatureColor}
          width={signatureWidth}
          maskSrc={signatureImageSrc}
        />

        {/* Title & Subtitle */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <span
            style={{
              fontSize: isVertical ? "52px" : "36px",
              fontWeight: 900,
              color: "#ffffff",
              letterSpacing: "0.5px",
              textShadow: "0 4px 16px rgba(0,0,0,0.5)",
            }}
          >
            {title}
          </span>
          <span
            style={{
              fontSize: isVertical ? "32px" : "22px",
              fontWeight: 500,
              color: "#d1e2d8",
            }}
          >
            {subtitle}
          </span>
        </div>

        {/* Website pill badge */}
        <div
          style={{
            marginTop: isVertical ? "16px" : "8px",
            background: "rgba(255, 255, 255, 0.12)",
            border: `1.5px solid ${signatureColor}`,
            padding: isVertical ? "16px 44px" : "10px 30px",
            borderRadius: "50px",
            color: signatureColor,
            fontSize: isVertical ? "34px" : "22px",
            fontWeight: 800,
            letterSpacing: "1px",
            boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
          }}
        >
          {websiteUrl}
        </div>
      </div>
    </AbsoluteFill>
  );
};
