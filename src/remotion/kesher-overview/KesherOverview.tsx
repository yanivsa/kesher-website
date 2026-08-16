import React from "react";
import {Video} from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {palette} from "./theme";
import type {KesherOverviewProps, MotionSegment} from "./types";

export const KesherOverview: React.FC<KesherOverviewProps> = ({
  videoSrc,
  audioSrc,
  title,
  category,
  url = "kesher.saharoni.com",
  motionPlan,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();

  // Primary source video path
  const mediaFile = videoSrc || audioSrc || "kesher-input.mp4";

  // Calculate current active motion plan segment
  const segments = motionPlan?.segments || [];
  const activeSegment: MotionSegment | undefined = segments.find(
    (seg) => frame >= seg.startFrame && frame <= seg.endFrame
  ) || segments[0];

  let scale = 1.0;
  let panX = 0.0;
  let panY = 0.0;
  let originX = 50.0;
  let originY = 50.0;

  if (activeSegment) {
    const segDuration = Math.max(1, activeSegment.endFrame - activeSegment.startFrame);
    const segProgress = Math.min(
      1.0,
      Math.max(0.0, (frame - activeSegment.startFrame) / segDuration)
    );

    originX = activeSegment.originX ?? 50.0;
    originY = activeSegment.originY ?? 50.0;

    if (activeSegment.transformType === "spring_emphasis") {
      const springVal = spring({
        frame: frame - activeSegment.startFrame,
        fps,
        config: {
          damping: activeSegment.springDamping ?? 12,
          stiffness: activeSegment.springStiffness ?? 80,
        },
      });
      scale = interpolate(
        springVal,
        [0, 1],
        [activeSegment.scaleStart, activeSegment.scaleEnd]
      );
      panX = interpolate(
        springVal,
        [0, 1],
        [activeSegment.panXStart, activeSegment.panXEnd]
      );
      panY = interpolate(
        springVal,
        [0, 1],
        [activeSegment.panYStart, activeSegment.panYEnd]
      );
    } else {
      const easedProgress = interpolate(segProgress, [0, 1], [0, 1], {
        easing: Easing.bezier(0.25, 0.1, 0.25, 1.0),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });

      scale = interpolate(
        easedProgress,
        [0, 1],
        [activeSegment.scaleStart, activeSegment.scaleEnd]
      );
      panX = interpolate(
        easedProgress,
        [0, 1],
        [activeSegment.panXStart, activeSegment.panXEnd]
      );
      panY = interpolate(
        easedProgress,
        [0, 1],
        [activeSegment.panYStart, activeSegment.panYEnd]
      );
    }
  }

  // Progress bar ratio
  const progress = frame / Math.max(durationInFrames - 1, 1);

  // Subtle intro animation for title card overlay
  const introOpacity = interpolate(frame, [0, 12, 120, 140], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{backgroundColor: palette.ink, overflow: "hidden"}}>
      {/* Continuous full-screen base video with frame-driven motion transforms */}
      <Video
        src={staticFile(mediaFile)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${panX}px, ${panY}px)`,
          transformOrigin: `${originX}% ${originY}%`,
          transition: "transform 0.05s linear",
        }}
      />

      {/* Subtle edge gradient overlays for safe readability without obscuring storytelling center */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(34,24,20,0.40) 0%, rgba(34,24,20,0.02) 25%, rgba(34,24,20,0.02) 75%, rgba(34,24,20,0.45) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* Top progress bar */}
      <div
        style={{
          position: "absolute",
          top: 24,
          left: 40,
          right: 40,
          height: 6,
          background: "rgba(255,255,255,0.25)",
          borderRadius: 3,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.round(progress * 100)}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${palette.gold}, ${palette.rose}, ${palette.clay})`,
          }}
        />
      </div>

      {/* Optional intro title overlay badge */}
      {title && (
        <div
          dir="rtl"
          style={{
            position: "absolute",
            top: 48,
            right: 40,
            opacity: introOpacity,
            background: "rgba(34,24,20,0.85)",
            padding: "10px 20px",
            borderRadius: 12,
            borderRight: `4px solid ${palette.gold}`,
            color: palette.cream,
            fontSize: 26,
            fontWeight: 800,
            fontFamily: "Arial, sans-serif",
            maxWidth: 600,
            boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
          }}
        >
          {title}
        </div>
      )}

      {/* Bottom corner brand badge */}
      <div
        style={{
          position: "absolute",
          left: 36,
          bottom: 28,
          background: "rgba(34,24,20,0.82)",
          padding: "8px 18px",
          borderRadius: 20,
          border: `1.5px solid ${palette.gold}`,
          color: palette.cream,
          fontFamily: "Arial, sans-serif",
          fontSize: 20,
          fontWeight: 800,
          letterSpacing: 0.2,
          boxShadow: "0 6px 18px rgba(0,0,0,0.25)",
        }}
      >
        {url.replace(/^https?:\/\//, "").replace(/\/$/, "")}
      </div>
    </AbsoluteFill>
  );
};
