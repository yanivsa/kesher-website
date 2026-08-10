import React from "react";
import { Composition } from "remotion";
import { ArticleShort } from "./ArticleShort";
import { KesherOverview } from "./kesher-overview/KesherOverview";
import type { KesherOverviewProps } from "./kesher-overview/types";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ArticleShort"
        component={ArticleShort as unknown as React.ComponentType<Record<string, unknown>>}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          title: "כותרת המאמר היומי",
          excerpt: "תקציר המאמר וטיפים זהב מתוך הקליניקה לחיים זוגיים ומשפחתיים שמחים יותר.",
          category: "זוגיות",
          image: ""
        }}
      />
      <Composition<KesherOverviewProps>
        id="KesherOverview"
        component={KesherOverview}
        durationInFrames={3120}
        fps={30}
        width={1280}
        height={720}
        calculateMetadata={({props}) => ({durationInFrames: props.durationInFrames})}
        defaultProps={{
          audioSrc: "kesher-input.mp4",
          durationInFrames: 3120,
          title: "איך לדבר כשהלב סגור",
          category: "זוגיות",
          url: "https://kesher.saharoni.com",
        }}
      />
    </>
  );
};
