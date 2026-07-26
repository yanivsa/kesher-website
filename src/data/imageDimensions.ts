const dimensions: Record<string, { width: number; height: number }> = {
  '/images/generated/site/home-hero.jpg': { width: 1600, height: 900 },
  '/images/generated/site/about-office.png': { width: 1024, height: 1024 },
  '/images/shira-saharoni.webp': { width: 1271, height: 1280 },
  '/images/generated/services/couples-room.jpg': { width: 1600, height: 900 },
  '/images/generated/services/parenting-room.jpg': { width: 1600, height: 900 },
  '/images/generated/services/couples-aliyah-relocation.webp': { width: 1600, height: 900 },
  '/images/generated/services/premarital-first-year.webp': { width: 1600, height: 900 },
  '/images/generated/blog/aliyah-partners-adjustment-pace.webp': { width: 1600, height: 900 },
  '/images/generated/blog/newlywed-first-year-conflicts.webp': { width: 1600, height: 900 },
  '/images/generated/blog/adhd-first-grade-preparation.jpg': { width: 1256, height: 1256 },
  '/images/generated/blog/couples-adhd-premarital-planning.jpg': { width: 1256, height: 1256 },
  '/images/generated/blog/adhd-and-screen-addiction-strategies.jpg': { width: 1600, height: 1000 },
  '/images/generated/blog/healing-after-infidelity.jpg': { width: 1600, height: 1000 },
  '/images/generated/blog/marriage-after-trust-leak.jpg': { width: 1600, height: 1000 },
  '/images/generated/blog/mediation-for-family-business-disputes.jpg': { width: 1600, height: 900 },
  '/images/generated/blog/mediation-for-will-conflicts.jpg': { width: 1600, height: 900 },
  '/images/generated/blog/parenting-teen-social-anxiety.jpg': { width: 1600, height: 900 },
  '/images/generated/blog/parenting-the-stubborn-child.jpg': { width: 1600, height: 900 },
  '/images/generated/blog/quiet-resignation.jpg': { width: 1600, height: 900 },
  '/images/generated/blog/relationship-after-childbirth.jpg': { width: 1600, height: 2400 },
  '/images/generated/blog/roman-empire.jpg': { width: 1600, height: 900 },
};

export const getImageDimensions = (src: string) =>
  dimensions[src] || { width: 512, height: 512 };
