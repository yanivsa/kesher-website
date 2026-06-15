import { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import Fuse from 'fuse.js';

type Post = {
  id: string;
  title: string;
  excerpt: string;
  category: string;
  subcategory?: string;
  image: string; date: string;
};

export const useBlogFilters = (posts: Post[]) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');

  const activeCategory = searchParams.get('category') || 'הכל';
  const activeSubcategory = searchParams.get('subcategory') || 'הכל';

  const handleCategoryChange = (category: string) => {
    setSearchParams(category === 'הכל' ? {} : { category });
  };

  const handleSubcategoryChange = (subcategory: string) => {
    const params: Record<string, string> = {};
    if (activeCategory !== 'הכל') params.category = activeCategory;
    if (subcategory !== 'הכל') params.subcategory = subcategory;
    setSearchParams(params);
  };

  const fuse = useMemo(() => new Fuse(posts, {
    keys: ['title', 'excerpt'],
    threshold: 0.3,
  }), [posts]);

  const filteredPosts = useMemo(() => {
    let result = searchQuery ? fuse.search(searchQuery).map(res => res.item) : posts;

    if (activeCategory !== 'הכל') {
      result = result.filter(post => post.category === activeCategory);
    }

    if (activeSubcategory !== 'הכל') {
      result = result.filter(post => 'subcategory' in post && post.subcategory === activeSubcategory);
    }

    return result;
  }, [posts, fuse, searchQuery, activeCategory, activeSubcategory]);

  const resetFilters = () => {
    setSearchQuery('');
    setSearchParams({});
  };

  return {
    searchQuery,
    setSearchQuery,
    activeCategory,
    activeSubcategory,
    handleCategoryChange,
    handleSubcategoryChange,
    filteredPosts,
    resetFilters,
  };
};
