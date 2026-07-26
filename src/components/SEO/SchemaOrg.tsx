import React from 'react';
import { serializeJsonLd } from '../../lib/serializeJsonLd';

interface SchemaOrgProps {
  data: object;
}

const SchemaOrg: React.FC<SchemaOrgProps> = ({ data }) => {
  return (
    <script
      type="application/ld+json"
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: serializeJsonLd(data) }}
    />
  );
};

export default SchemaOrg;
