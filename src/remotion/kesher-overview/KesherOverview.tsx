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
import type {EnhancementTimelineEntry, KesherOverviewProps, MotionSegment} from "./types";
import {FullScreenSignatureOutro} from "../components/FullScreenSignatureOutro";
import {
  EnhancementAssetOverlay,
  type EnhancementAssetType,
} from "../components/EnhancementAssetOverlay";

type PlannedAsset = EnhancementTimelineEntry & {
  asset_ref: string;
  type: EnhancementAssetType;
};

const isPlannedAsset = (entry: EnhancementTimelineEntry): entry is PlannedAsset =>
  Boolean(entry.asset_ref) &&
  (entry.type === "image" || entry.type === "broll" || entry.type === "motion_graphic");

export const KesherOverview: React.FC<KesherOverviewProps> = ({
  videoSrc,
  audioSrc,
  title,
  _category,
  url = "kesher.saharoni.com",
  motionPlan,
}: KesherOverviewProps & {_category?: string}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  const mediaFile = videoSrc || audioSrc || "kesher-input.mp4";
  const segments = motionPlan?.segments || [];
  const plannedAssets = (motionPlan?.timeline || []).filter(isPlannedAsset);
  const activeSegment: MotionSegment | undefined = segments.find(
    (seg) => frame >= seg.startFrame && frame <= seg.endFrame,
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
      Math.max(0.0, (frame - activeSegment.startFrame) / segDuration),
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
        [activeSegment.scaleStart, activeSegment.scaleEnd],
      );
      panX = interpolate(
        springVal,
        [0, 1],
        [activeSegment.panXStart, activeSegment.panXEnd],
      );
      panY = interpolate(
        springVal,
        [0, 1],
        [activeSegment.panYStart, activeSegment.panYEnd],
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
        [activeSegment.scaleStart, activeSegment.scaleEnd],
      );
      panX = interpolate(
        easedProgress,
        [0, 1],
        [activeSegment.panXStart, activeSegment.panXEnd],
      );
      panY = interpolate(
        easedProgress,
        [0, 1],
        [activeSegment.panYStart, activeSegment.panYEnd],
      );
    }
  }

  const progress = frame / Math.max(durationInFrames - 1, 1);
  const introOpacity = interpolate(frame, [0, 12, 120, 140], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{backgroundColor: palette.ink, overflow: "hidden"}}>
      <Video
        src={staticFile(mediaFile)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${panX}px, ${panY}px)`,
          transformOrigin: `${originX}% ${originY}%`,
        }}
      />

      {plannedAssets.map((entry, index) => {
        const startFrame = Math.max(0, Math.round(entry.start * fps));
        const endFrame = Math.max(startFrame, Math.round(entry.end * fps));
        return (
          <EnhancementAssetOverlay
            key={`${entry.asset_ref}-${index}`}
            assetRef={entry.asset_ref}
            assetType={entry.type}
            startFrame={startFrame}
            endFrame={endFrame}
          />
        );
      })}

      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(34,24,20,0.40) 0%, rgba(34,24,20,0.02) 25%, rgba(34,24,20,0.02) 75%, rgba(34,24,20,0.45) 100%)",
          pointerEvents: "none",
        }}
      />

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

      <FullScreenSignatureOutro
        durationSeconds={3}
        backgroundColor={`linear-gradient(135deg, ${palette.ink} 0%, #0d1712 100%)`}
        signatureColor={palette.gold}
        websiteUrl={url.replace(/^https?:\/\//, "").replace(/\/$/, "")}
      />
    </AbsoluteFill>
  );
};
