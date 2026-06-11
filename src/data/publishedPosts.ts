import posts from './posts.json';

const wordCount = (html: string) =>
  html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;

export const isPublishablePost = (post: (typeof posts)[number]) =>
  wordCount(post.content) >= 500 &&
  (post.content.match(/<h3/g) || []).length >= 5;

const publishedPosts = posts.filter(isPublishablePost);

export default publishedPosts;
