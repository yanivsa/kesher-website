# Internal article link gate

Two assisted article recoveries exposed invented internal URLs despite passing the minimum-link-count policy: PR1209 used toddler-tantrums-causes; PR1213 used sleep-routine and morning-routine. Those destinations do not exist in the active or archived article catalogs.

The trusted publication content gate now parses HTML anchor destinations and rejects missing internal /blog/ targets before image reads or publication. It includes the exact head catalog plus the archived catalog, handles URL-encoded slugs, query strings, fragments, trailing slashes and unquoted HTML attributes, and leaves external sites to their own link policy. A link count alone is no longer sufficient proof of working destinations.

Validation: observed RED→GREEN tests;90focused keyword/publication/quality tests pass. Authority changes recertify existing hashes only.
