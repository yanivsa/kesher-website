export type MotionSegment = {
  startFrame: number;
  endFrame: number;
  transformType: "push_in" | "pan_right" | "scale_up" | "pan_left" | "tracked_reframe" | "spring_emphasis";
  scaleStart: number;
  scaleEnd: number;
  panXStart: number;
  panXEnd: number;
  panYStart: number;
  panYEnd: number;
  originX: number;
  originY: number;
  springDamping?: number;
  springStiffness?: number;
};

export type MotionPlan = {
  version: number;
  video_sha256?: string;
  durationInFrames: number;
  fps: number;
  segments: MotionSegment[];
};

export type KesherOverviewProps = {
  videoSrc?: string;
  audioSrc?: string;
  durationInFrames: number;
  title: string;
  category: string;
  url: string;
  motionPlan?: MotionPlan;
};
