# Music Generation (continued 2/2)

## Limitations

- **Instrumental only**: No vocal/singing generation
- **WebSocket required**: Real-time streaming connection
- **Safety filtering**: Prompts undergo safety review
- **Watermarking**: All output contains SynthID watermark
- **Experimental**: API may change

## Best Practices

1. **Buffer audio**: Implement robust buffering for smooth playback
2. **Gradual transitions**: Avoid drastic prompt changes mid-stream
3. **Sparse for backgrounds**: Lower density for video backgrounds
4. **Test prompts**: Iterate on prompt combinations
5. **Cross-fade transitions**: Blend audio at style changes
6. **Match video mood**: Align music tempo/energy with visuals

## Resources

- [Lyria RealTime Docs](https://ai.google.dev/gemini-api/docs/music-generation)
- [Audio Processing Guide](./audio-processing.md)
- [Video Generation](./video-generation.md)

---

**Related**: [Audio Processing](./audio-processing.md) | [Video Generation](./video-generation.md)

**Back to**: [AI Multimodal Skill](../SKILL.md)
