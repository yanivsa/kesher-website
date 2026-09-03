import React from "react";
import {Video} from "@remotion/media";
import {
  AbsoluteFill,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export interface ArticleShortProps {
  videoSrc: string;
  sourceStartFrame: number;
  durationInFrames: number;
  title: string;
  category: string;
  url: string;
}

export const ArticleShort: React.FC<ArticleShortProps> = ({
  videoSrc,
  sourceStartFrame,
  durationInFrames,
  title,
  category,
  url,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = interpolate(frame, [0, Math.max(1, Math.round(0.45 * fps))], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const outroStart = Math.max(0, durationInFrames - Math.round(2.5 * fps));
  const outro = interpolate(frame, [outroStart, durationInFrames - 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{backgroundColor: "#101714"}}>
      <Video
        src={staticFile(videoSrc)}
        trimBefore={sourceStartFrame}
        durationInFrames={durationInFrames}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: "center center",
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
          opacity: Math.max(0.78, outro),
          fontFamily: "Heebo, Rubik, Arial, sans-serif",
          color: "white",
          fontSize: 30,
          fontWeight: 800,
          textShadow: "0 2px 14px rgba(0,0,0,0.8)",
        }}
      >
        שירה סהרוני · {url}
      </div>
    </AbsoluteFill>
  );
};
