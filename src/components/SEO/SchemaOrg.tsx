import React from 'react';

interface SchemaOrgProps {
  data: object;
}

const SchemaOrg: React.FC<SchemaOrgProps> = ({ data }) => {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
};

export default SchemaOrg;
