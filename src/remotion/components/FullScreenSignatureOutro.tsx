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
  backgroundColor = "linear-gradient(180deg, #0d1712 0%, #15271e 100%)",
  signatureColor = "#f4d068",
  signatureImageSrc = "signature-mask.svg",
  title = "שירה סהרוני",
  subtitle = "ייעוץ זוגי והנחיית הורים",
  websiteUrl = "kesher.saharoni.com",
  zIndex = 9999,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width } = useVideoConfig();

  const overlayLengthFrames = Math.round(durationSeconds * fps);
  const startFrame = Math.max(0, durationInFrames - overlayLengthFrames);

  // The approved signature treatment, including its branded background, lives inside the existing source timeline. It never appends frames.
  if (frame < startFrame) {
    return null;
  }

  const current = frame - startFrame;

  const overlayOpacity = interpolate(current, [0, Math.min(10, overlayLengthFrames * 0.2)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cardScale = spring({
    frame: current,
    fps,
    config: { damping: 14, stiffness: 90 },
  });

  const isVertical = width < 1200;
  const signatureWidth = isVertical ? "75%" : "480px";

  return (
    <AbsoluteFill
      style={{
        zIndex,
        background: backgroundColor,
        opacity: overlayOpacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "60px 40px",
        direction: "rtl",
        fontFamily: "'Heebo', 'Rubik', Arial, sans-serif",
        pointerEvents: "none",
      }}
    >
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
        <RemotionSignature
          startFrame={startFrame + 5}
          durationInFrames={Math.max(1, Math.min(38, overlayLengthFrames - 10))}
          color={signatureColor}
          width={signatureWidth}
          maskSrc={signatureImageSrc}
        />

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
              textShadow: "0 2px 12px rgba(0,0,0,0.65)",
            }}
          >
            {subtitle}
          </span>
        </div>

        <div
          style={{
            marginTop: isVertical ? "16px" : "8px",
            background: "rgba(13, 23, 18, 0.50)",
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
