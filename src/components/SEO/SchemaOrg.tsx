import React from 'react';

interface SchemaOrgProps {
  data: object;
}

const SchemaOrg: React.FC<SchemaOrgProps> = ({ data }) => {
  return (
    <script type="application/ld+json">
      {JSON.stringify(data)}
    </script>
  );
};

export default SchemaOrg;
