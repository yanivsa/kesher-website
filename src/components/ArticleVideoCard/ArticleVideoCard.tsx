import React, { useId, useState } from 'react';
import styles from './ArticleVideoCard.module.css';

interface ArticleVideoCardProps {
  youtubeId: string;
  title: string;
  poster?: string;
}

const YOUTUBE_ID_PATTERN = /^[A-Za-z0-9_-]{6,20}$/;

const ArticleVideoCard: React.FC<ArticleVideoCardProps> = ({ youtubeId, title, poster }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const headingId = useId();

  if (!YOUTUBE_ID_PATTERN.test(youtubeId)) return null;

  const watchUrl = `https://www.youtube.com/watch?v=${encodeURIComponent(youtubeId)}`;
  const embedUrl = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(youtubeId)}?autoplay=1&rel=0`;

  return (
    <section className={styles.card} aria-labelledby={headingId}>
      {isPlaying ? (
        <div className={styles.playerShell}>
          <iframe
            className={styles.player}
            src={embedUrl}
            title={`סרטון: ${title}`}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      ) : (
        <button
          type="button"
          className={styles.facade}
          onClick={() => setIsPlaying(true)}
          aria-label={`נגן את הסרטון: ${title}`}
        >
          {poster ? (
            <img
              src={poster}
              alt=""
              className={styles.poster}
              loading="lazy"
              decoding="async"
            />
          ) : (
            <span className={styles.posterFallback} aria-hidden="true" />
          )}
          <span className={styles.shade} aria-hidden="true" />
          <span className={styles.badge}>וידאו של המאמר</span>
          <span className={styles.playButton} aria-hidden="true">
            <span className={styles.playIcon}>▶</span>
          </span>
          <span className={styles.facadeCaption}>לחצו לצפייה בלי להכביד על טעינת העמוד</span>
        </button>
      )}

      <div className={styles.meta}>
        <div className={styles.copy}>
          <span className={styles.eyebrow}>גם בווידאו</span>
          <h2 id={headingId}>מעדיפים לצפות?</h2>
          <p>צפו בסרטון שמסכם ומרחיב את הנושא של המאמר.</p>
        </div>
        <a
          className={styles.youtubeLink}
          href={watchUrl}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`פתיחת הסרטון ביוטיוב: ${title}`}
        >
          פתיחה ב‑YouTube <span aria-hidden="true">↗</span>
        </a>
      </div>
    </section>
  );
};

export default ArticleVideoCard;
