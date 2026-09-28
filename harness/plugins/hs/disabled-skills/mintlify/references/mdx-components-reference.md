# MDX Components Reference

Reference for all 26+ Mintlify MDX components.

## Structure Content

### Tabs

Organize content into tabbed sections.

```mdx
<Tabs>
  <Tab title="JavaScript">
    JavaScript content here
  </Tab>
  <Tab title="Python">
    Python content here
  </Tab>
  <Tab title="Go">
    Go content here
  </Tab>
</Tabs>
```

### Code Groups

Display code examples in multiple languages with syntax highlighting.

```mdx
<CodeGroup>
```bash npm
npm install package
```

```bash yarn
yarn add package
```

```bash pnpm
pnpm add package
```
</CodeGroup>
```

### Steps

Create numbered step-by-step instructions.

```mdx
<Steps>
  <Step title="Install dependencies">
    Run `npm install` to install required packages.
  </Step>
  <Step title="Configure environment">
    Create `.env` file with your API keys.
  </Step>
  <Step title="Start the server">
    Run `npm start` to launch the application.
  </Step>
</Steps>
```

### Columns

Create multi-column layouts.

```mdx
<Columns>
  <Column>
    Content in first column
  </Column>
  <Column>
    Content in second column
  </Column>
  <Column>
    Content in third column
  </Column>
</Columns>
```

### Panel

Create bordered content panels.

```mdx
<Panel>
  This content appears in a bordered panel.
</Panel>
```

## Draw Attention

### Callouts

Four types of callouts for different message types.

```mdx
<Note>
  This is a general note or information.
</Note>

<Warning>
  This is a warning about potential issues.
</Warning>

<Tip>
  This is a helpful tip or best practice.
</Tip>

<Info>
  This is informational content.
</Info>

<Check>
  This indicates success or completion.
</Check>
```

### Banner

Display prominent banners at the top of pages.

```mdx
<Banner>
  Important announcement or message
</Banner>
```

### Badge

Add inline badges for labels or statuses.

```mdx
<Badge>New</Badge>
<Badge variant="success">Available</Badge>
<Badge variant="warning">Beta</Badge>
<Badge variant="danger">Deprecated</Badge>
```

### Update

Highlight recent updates or changelog entries.

```mdx
<Update date="2024-01-15">
  Added new authentication methods
</Update>
```

### Frames

Embed iframes or external content.

```mdx
<Frame>
  <iframe src="https://example.com/demo" width="100%" height="400px" />
</Frame>

<Frame caption="Interactive demo">
  <img src="/images/screenshot.png" alt="Screenshot" />
</Frame>
```

### Tooltips

Add hover tooltips to text.

```mdx
<Tooltip tip="This is additional context">
  Hover over this text
</Tooltip>
```

## Show/Hide

### Accordions

Create collapsible accordion sections.

```mdx
<AccordionGroup>
  <Accordion title="What is Mintlify?">
    Mintlify is a modern documentation platform that helps you create beautiful docs.
  </Accordion>
  <Accordion title="How do I get started?">
    Run `mint new` to create a new documentation project.
  </Accordion>
  <Accordion title="Can I use custom components?">
    Yes, you can use React components in your MDX files.
  </Accordion>
</AccordionGroup>
```

### Expandables

Create expandable content sections.

```mdx
<Expandable title="Click to expand">
  Hidden content that appears when expanded.
</Expandable>

<Expandable title="Advanced configuration" defaultOpen={true}>
  This content is expanded by default.
</Expandable>
```

### View

Show/hide content based on conditions.

```mdx
<View if="api">
  This content only shows for API documentation.
</View>

<View ifNot="mobile">
  This content is hidden on mobile devices.
</View>
```


---

Continued in [mdx-components-reference-cont.md](mdx-components-reference-cont.md)
