import React from "react";
import {Video} from "@remotion/media";
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

export type EnhancementAssetType = "image" | "broll" | "motion_graphic";

export type EnhancementAssetOverlayProps = {
  assetRef?: string;
  assetType?: EnhancementAssetType;
  startFrame: number;
  endFrame: number;
};

const AssetBody: React.FC<{
  assetRef: string;
  assetType: EnhancementAssetType;
  durationInFrames: number;
}> = ({assetRef, assetType, durationInFrames}) => {
  const frame = useCurrentFrame();
  const fadeFrames = Math.max(1, Math.min(8, Math.floor(durationInFrames / 4)));
  const opacity = interpolate(
    frame,
    [0, fadeFrames, Math.max(fadeFrames, durationInFrames - fadeFrames), durationInFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
  );
  const scale = interpolate(frame, [0, Math.max(1, durationInFrames)], [1.035, 1.0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const src = staticFile(assetRef);

  return (
    <AbsoluteFill style={{opacity, backgroundColor: "#101714"}}>
      {assetType === "broll" ? (
        <Video
          src={src}
          muted
          style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})`}}
        />
      ) : (
        <Img
          src={src}
          style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})`}}
        />
      )}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(8,14,11,0.10) 0%, rgba(8,14,11,0.02) 55%, rgba(8,14,11,0.22) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

/**
 * Optional visual-only layer. The authoritative NotebookLM Video component
 * stays mounted underneath, so its exact narration/audio remains untouched.
 */
export const EnhancementAssetOverlay: React.FC<EnhancementAssetOverlayProps> = ({
  assetRef,
  assetType,
  startFrame,
  endFrame,
}) => {
  if (!assetRef || !assetType || !["image", "broll", "motion_graphic"].includes(assetType)) {
    return null;
  }
  const from = Math.max(0, Math.round(startFrame));
  const durationInFrames = Math.max(1, Math.round(endFrame) - from + 1);
  return (
    <Sequence from={from} durationInFrames={durationInFrames} premountFor={12}>
      <AssetBody assetRef={assetRef} assetType={assetType} durationInFrames={durationInFrames} />
    </Sequence>
  );
};
