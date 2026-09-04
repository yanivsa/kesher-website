import React from "react";
import {Video} from "@remotion/media";
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export interface MotionTarget {
  startFrame: number;
  endFrame: number;
  focusX: number;
  focusY: number;
  zoom: number;
  rotation: number;
}

export interface ArticleShortProps {
  videoSrc: string;
  sourceStartFrame: number;
  durationInFrames: number;
  title: string;
  category: string;
  url: string;
  signatureImageSrc?: string;
  motionPlan?: MotionTarget[];
}

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
const SIGNATURE_SECONDS = 3;

export const ArticleShort: React.FC<ArticleShortProps> = ({
  videoSrc,
  sourceStartFrame,
  durationInFrames,
  title,
  category,
  url,
  signatureImageSrc = "signature-mask.svg",
  motionPlan = [],
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = interpolate(frame, [0, Math.max(1, Math.round(0.45 * fps))], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const signatureDurationFrames = Math.round(SIGNATURE_SECONDS * fps);
  const signatureStart = Math.max(0, durationInFrames - signatureDurationFrames);

  const target = motionPlan.find(
    (entry) => frame >= entry.startFrame && frame <= entry.endFrame,
  );
  const targetSpan = target ? Math.max(1, target.endFrame - target.startFrame) : 1;
  const targetProgress = target ? clamp01((frame - target.startFrame) / targetSpan) : 0;
  const pulse = Math.sin(targetProgress * Math.PI);
  const zoom = target ? 1 + (Math.max(1.08, target.zoom) - 1) * pulse : 1;
  const focusX = target ? clamp01(target.focusX) : 0.5;
  const focusY = target ? clamp01(target.focusY) : 0.5;
  const translateX = target ? (0.5 - focusX) * 110 * pulse : 0;
  const translateY = target ? (0.5 - focusY) * 170 * pulse : 0;
  const rotation = target ? target.rotation * pulse : 0;

  return (
    <AbsoluteFill style={{backgroundColor: "#101714", overflow: "hidden"}}>
      <Video
        src={staticFile(videoSrc)}
        trimBefore={sourceStartFrame}
        durationInFrames={durationInFrames}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: "center center",
          transform: `scale(${zoom}) translate(${translateX}px, ${translateY}px) rotate(${rotation}deg)`,
          transformOrigin: "center center",
        }}
      />

      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(6,14,10,0.68) 0%, rgba(6,14,10,0.08) 25%, rgba(6,14,10,0.04) 64%, rgba(6,14,10,0.76) 100%)",
        }}
      />

      <div
        style={{
          position: "absolute",
          top: 76,
          left: 54,
          right: 54,
          direction: "rtl",
          textAlign: "right",
          opacity: intro,
          translate: `0 ${interpolate(intro, [0, 1], [-18, 0])}px`,
          fontFamily: "Heebo, Rubik, Arial, sans-serif",
          color: "white",
          textShadow: "0 3px 18px rgba(0,0,0,0.72)",
        }}
      >
        <div
          style={{
            display: "inline-block",
            padding: "9px 20px",
            borderRadius: 999,
            backgroundColor: "rgba(29,72,52,0.88)",
            fontSize: 30,
            fontWeight: 700,
            marginBottom: 18,
          }}
        >
          {category}
        </div>
        <div
          style={{
            fontSize: 54,
            lineHeight: 1.12,
            fontWeight: 900,
            maxWidth: 930,
          }}
        >
          {title}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: 52,
          right: 52,
          bottom: 76,
          direction: "rtl",
          textAlign: "center",
          fontFamily: "Heebo, Rubik, Arial, sans-serif",
          color: "white",
          fontSize: 30,
          fontWeight: 800,
          textShadow: "0 2px 14px rgba(0,0,0,0.8)",
        }}
      >
        שירה סהרוני · {url}
      </div>

      <Sequence from={signatureStart} durationInFrames={signatureDurationFrames}>
        <AbsoluteFill
          style={{
            backgroundColor: "white",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Img
            src={staticFile(signatureImageSrc)}
            style={{
              width: "88%",
              height: "88%",
              objectFit: "contain",
              objectPosition: "center center",
            }}
          />
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};
