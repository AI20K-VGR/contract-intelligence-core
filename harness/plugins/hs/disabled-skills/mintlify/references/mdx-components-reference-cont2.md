# MDX Components Reference (continued 3/3)

## Page Frontmatter

All MDX pages support frontmatter for metadata and configuration.

```mdx
---
title: "Page Title"
description: "SEO description"
icon: "rocket"
mode: "wide"
---

Page content here...
```

**Common frontmatter fields:**
- `title` - Page title
- `description` - SEO description
- `icon` - Page icon
- `mode` - Layout mode (default, wide, custom, frame, center)
- `sidebarTitle` - Custom sidebar title
- `openapi` - OpenAPI operation (e.g., "GET /users")

**Mode options:**
- `default` - Standard content width
- `wide` - Wider content area
- `custom` - Full-width custom layout
- `frame` - Embedded frame (Aspen/Almond themes only)
- `center` - Centered content (Mint/Linden themes only)

## React Components

Import and use custom React components in MDX.

```mdx
---
title: "Custom Components"
---

import { CustomButton } from '@/components/CustomButton'
import { Chart } from '@/components/Chart'

<CustomButton onClick={() => console.log('clicked')}>
  Click me
</CustomButton>

<Chart data={[1, 2, 3, 4, 5]} />
```

Place custom components in `/components` or configure import paths in your build setup.
