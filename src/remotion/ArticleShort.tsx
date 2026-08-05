import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface ArticleShortProps {
  title: string;
  excerpt: string;
  category: string;
  image?: string;
}

export const ArticleShort: React.FC<ArticleShortProps> = ({
  title,
  excerpt,
  category,
  image
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({ frame, fps, config: { damping: 12 } });
  const contentSpring = spring({ frame: frame - 30, fps, config: { damping: 14 } });
  const ctaSpring = spring({ frame: frame - 60, fps, config: { damping: 15 } });

  const bgHue = interpolate(frame, [0, 900], [140, 200]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(135deg, hsl(${bgHue}, 45%, 20%), hsl(${bgHue + 40}, 55%, 12%))`,
        fontFamily: "'Heebo', 'Rubik', sans-serif",
        color: "#ffffff",
        direction: "rtl",
        padding: "80px 60px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        alignItems: "center",
        textAlign: "center"
      }}
    >
      {/* Background Image with Blur & Dark Overlay */}
      {image && (
        <AbsoluteFill style={{ opacity: 0.25, filter: "blur(8px)" }}>
          <img src={image} style={{ width: "100%", height: "100%", objectFit: "cover" }} alt="" />
        </AbsoluteFill>
      )}

      {/* Top Header Badge */}
      <div
        style={{
          transform: `scale(${titleSpring})`,
          background: "linear-gradient(90deg, #7c9e87, #4a7c59)",
          padding: "16px 40px",
          borderRadius: "50px",
          fontSize: "36px",
          fontWeight: 800,
          boxShadow: "0 10px 30px rgba(0,0,0,0.3)"
        }}
      >
        {category || "ייעוץ זוגי והדרכת הורים"}
      </div>

      {/* Main Title & Excerpt */}
      <div style={{ zIndex: 2, margin: "auto 0" }}>
        <h1
          style={{
            transform: `translateY(${interpolate(titleSpring, [0, 1], [50, 0])}px)`,
            opacity: titleSpring,
            fontSize: "64px",
            lineHeight: 1.25,
            fontWeight: 900,
            textShadow: "0 4px 20px rgba(0,0,0,0.6)",
            marginBottom: "40px",
            color: "#ffffff"
          }}
        >
          {title}
        </h1>

        <div
          style={{
            transform: `translateY(${interpolate(contentSpring, [0, 1], [40, 0])}px)`,
            opacity: contentSpring,
            background: "rgba(255, 255, 255, 0.12)",
            backdropFilter: "blur(12px)",
            borderRadius: "24px",
            padding: "40px",
            border: "1px solid rgba(255, 255, 255, 0.2)",
            boxShadow: "0 20px 40px rgba(0,0,0,0.3)"
          }}
        >
          <p
            style={{
              fontSize: "40px",
              lineHeight: 1.4,
              fontWeight: 500,
              color: "#f0f4f1",
              margin: 0
            }}
          >
            {excerpt}
          </p>
        </div>
      </div>

      {/* Bottom CTA Footer */}
      <div
        style={{
          transform: `scale(${ctaSpring})`,
          opacity: ctaSpring,
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "16px"
        }}
      >
        <div
          style={{
            background: "linear-gradient(90deg, #e6af2e, #f4d068)",
            color: "#1a2e22",
            padding: "20px 60px",
            borderRadius: "50px",
            fontSize: "40px",
            fontWeight: 900,
            boxShadow: "0 10px 30px rgba(230, 175, 46, 0.4)"
          }}
        >
          לקריאת המאמר המלא ↺
        </div>
        <span style={{ fontSize: "32px", color: "rgba(255,255,255,0.8)", fontWeight: 700 }}>
          שירה סהרוני | kesher.saharoni.com
        </span>
      </div>
    </AbsoluteFill>
  );
};
