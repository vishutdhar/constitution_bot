import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Audio } from "@remotion/media";

/**
 * Constitution Bot — one vertical (1080x1920) video per day.
 *
 * Each day's source image (images_v2/day_NN_*.png) is a finished parchment
 * card that ALREADY contains that day's constitutional text in calligraphy.
 * So the artwork is the hero and we do NOT overlay competing body text — the
 * motion (slow push-in, light sweep, warm lamp flicker, fades, progress bar)
 * is alignment-free, so nothing can drift against the baked text.
 *
 * Per-day data arrives as input props (see data/days.json).
 */

export type DayProps = {
  day: number;
  section: string;
  hashtags: string;
  image: string; // path under public/, e.g. "images_v2/day_01_preamble.png"
  audio: string; // path under public/, e.g. "audio_male/day_01.mp3"
  durationInFrames: number;
  text?: string;
  audioSeconds?: number;
};

const SERIF =
  "Georgia, 'Iowan Old Style', 'Palatino Linotype', Palatino, 'Times New Roman', serif";
const SANS = "-apple-system, 'Helvetica Neue', Arial, sans-serif";

const GOLD = "#e7c873";
const PARCHMENT = "#f6edd8";
const INK = "#0b0e16";

const HANDLE = "@USC1787";
const TOTAL_DAYS = 77;

const EASE = Easing.bezier(0.16, 1, 0.3, 1);

const KenBurnsBackground: React.FC<{ image: string }> = ({ image }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.12], {
    extrapolateRight: "clamp",
  });
  const driftY = interpolate(frame, [0, durationInFrames], [0, -28], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: INK, overflow: "hidden" }}>
      <Img
        src={staticFile(image)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          scale,
          translate: `0px ${driftY}px`,
        }}
      />
    </AbsoluteFill>
  );
};

const LampGlow: React.FC = () => {
  const frame = useCurrentFrame();
  // Deterministic flicker (no Math.random): two out-of-phase sines.
  const flicker = 0.56 + 0.16 * Math.sin(frame / 5) + 0.06 * Math.sin(frame / 1.7);
  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(circle at 82% 15%, rgba(255,193,92,0.5) 0%, rgba(255,168,58,0.14) 17%, transparent 40%)",
        mixBlendMode: "screen",
        opacity: flicker,
      }}
    />
  );
};

const LightSweep: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const x = interpolate(frame, [0, durationInFrames], [-760, 1840], {
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          width: "55%",
          translate: `${x}px 0px`,
          background:
            "linear-gradient(105deg, transparent 0%, rgba(255,244,214,0.08) 44%, rgba(255,255,255,0.20) 50%, rgba(255,244,214,0.08) 56%, transparent 100%)",
          mixBlendMode: "soft-light",
        }}
      />
    </AbsoluteFill>
  );
};

const LegibilityWash: React.FC = () => (
  <>
    <AbsoluteFill
      style={{
        background:
          "linear-gradient(180deg, rgba(11,14,22,0.72) 0%, rgba(11,14,22,0.10) 22%, rgba(11,14,22,0.10) 60%, rgba(11,14,22,0.84) 100%)",
      }}
    />
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(118% 78% at 50% 44%, transparent 56%, rgba(0,0,0,0.5) 100%)",
      }}
    />
  </>
);

const Header: React.FC<{ day: number }> = ({ day }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [6, 26], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const translateY = interpolate(frame, [6, 26], [-18, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: 116 }}>
      <div
        style={{
          opacity,
          translate: `0px ${translateY}px`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 14,
        }}
      >
        <div
          style={{
            fontFamily: SANS,
            fontSize: 29,
            letterSpacing: 8,
            fontWeight: 700,
            color: GOLD,
            textShadow: "0 2px 12px rgba(0,0,0,0.7)",
          }}
        >
          THE U.S. CONSTITUTION
        </div>
        <div style={{ width: 116, height: 3, backgroundColor: GOLD, borderRadius: 2 }} />
        <div
          style={{
            fontFamily: SERIF,
            fontSize: 40,
            fontWeight: 600,
            color: PARCHMENT,
            textShadow: "0 2px 16px rgba(0,0,0,0.75)",
          }}
        >
          Day {day} of {TOTAL_DAYS}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Footer: React.FC<{ hashtags: string }> = ({ hashtags }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const opacity = interpolate(frame, [12, 32], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE,
  });
  const progress = interpolate(frame, [0, durationInFrames - 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Normalize spacing so the per-day hashtag string reads evenly.
  const tags = hashtags.trim().split(/\s+/).join("   ");

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center" }}>
      <div
        style={{
          opacity,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
          paddingBottom: 92,
          paddingLeft: 60,
          paddingRight: 60,
        }}
      >
        <div
          style={{
            fontFamily: SANS,
            fontSize: 40,
            fontWeight: 700,
            color: PARCHMENT,
            textShadow: "0 2px 14px rgba(0,0,0,0.8)",
          }}
        >
          {HANDLE}
        </div>
        <div
          style={{
            fontFamily: SANS,
            fontSize: 27,
            fontWeight: 600,
            color: GOLD,
            letterSpacing: 1,
            textAlign: "center",
            textShadow: "0 2px 12px rgba(0,0,0,0.8)",
          }}
        >
          {tags}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          width: "100%",
          height: 6,
          backgroundColor: "rgba(255,255,255,0.14)",
        }}
      >
        <div style={{ height: "100%", width: `${progress * 100}%`, backgroundColor: GOLD }} />
      </div>
    </AbsoluteFill>
  );
};

export const ConstitutionDay: React.FC<DayProps> = ({ day, hashtags, image, audio }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const masterOpacity = interpolate(
    frame,
    [0, 14, durationInFrames - 16, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      <Audio src={staticFile(audio)} />
      <AbsoluteFill style={{ opacity: masterOpacity }}>
        <KenBurnsBackground image={image} />
        <LampGlow />
        <LightSweep />
        <LegibilityWash />
        <Header day={day} />
        <Footer hashtags={hashtags} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
