import { describe, expect, it } from 'vitest';
import { serializeJsonLd } from '../src/lib/serializeJsonLd';

describe('SchemaOrg JSON-LD serialization', () => {
  it('keeps script-closing sequences inside JSON data', () => {
    const serialized = serializeJsonLd({
      title: '</script><script>alert("xss")</script>',
    });

    expect(serialized).not.toContain('</script>');
    expect(JSON.parse(serialized)).toEqual({
      title: '</script><script>alert("xss")</script>',
    });
  });
});
