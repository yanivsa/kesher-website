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

export type EnhancementTimelineType =
  | "broll"
  | "image"
  | "motion_graphic"
  | "push_in"
  | "pan"
  | "reframe"
  | "transition"
  | "lower_third"
  | "visual_hook"
  | "source_video";

export type EnhancementTimelineEntry = {
  start: number;
  end: number;
  type: EnhancementTimelineType;
  intent?: string;
  asset_ref?: string;
  fallback?: string;
  provenance?: string;
  source?: string;
  usage_status?: string;
  semantic_fit?: number;
  sha256?: string;
};

export type MotionPlan = {
  version: number;
  video_sha256?: string;
  durationInFrames: number;
  fps: number;
  segments: MotionSegment[];
  enhancement_schema_version?: number;
  source_identity?: string;
  profile?: string;
  product?: string;
  output?: {width: number; height: number; fps: number};
  render_mode?: string;
  timeline?: EnhancementTimelineEntry[];
  assets_used?: Record<string, unknown>[];
  assets_dropped?: Record<string, unknown>[];
  enhancement_status?: string;
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
