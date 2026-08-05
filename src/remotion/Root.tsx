import React from "react";
import { Composition } from "remotion";
import { ArticleShort } from "./ArticleShort";

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
    </>
  );
};
