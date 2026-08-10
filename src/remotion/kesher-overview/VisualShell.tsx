import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {palette} from "./theme";

export const VisualShell: React.FC<React.PropsWithChildren<{url?: string}>> = ({
  children,
  url = "https://kesher.saharoni.com",
}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const drift = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [-30, 30]);

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        background: `radial-gradient(circle at ${35 + drift / 10}% 22%, #fffdf9 0, ${palette.cream} 35%, #f4e7dc 100%)`,
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 520,
          height: 520,
          left: -170 + drift,
          top: -210,
          borderRadius: "48% 52% 62% 38%",
          background: `${palette.gold}55`,
          rotate: `${frame / 18}deg`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          right: -240 - drift,
          bottom: -320,
          borderRadius: "58% 42% 46% 54%",
          background: `${palette.rose}45`,
          rotate: `${-frame / 22}deg`,
        }}
      />
      {children}
      <div
        style={{
          position: "absolute",
          left: 42,
          bottom: 30,
          color: palette.ink,
          fontSize: 28,
          fontWeight: 800,
          letterSpacing: 0.1,
          opacity: 0.82,
        }}
      >
        {url}
      </div>
    </AbsoluteFill>
  );
};
