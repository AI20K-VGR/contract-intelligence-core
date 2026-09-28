# Turborepo Caching Strategies (continued 3/3)

## Best Practices

1. **Define precise outputs** - Only cache necessary files
2. **Exclude nested caches** - Don't cache caches (.next/cache)
3. **Use remote caching** - Share cache across team and CI
4. **Track relevant inputs** - Use `inputs` to filter files
5. **Separate env vars** - Use `passThroughEnv` for debug flags
6. **Cache test results** - Include coverage in outputs
7. **Don't cache dev servers** - Set `cache: false` for dev tasks
8. **Use global dependencies** - Share config across packages
9. **Monitor cache performance** - Use `--summarize` to analyze
10. **Clear cache periodically** - Remove stale cache manually

## Cache Performance Tips

**For CI/CD:**
- Enable remote caching
- Run only changed packages: `--filter='...[origin/main]'`
- Use `--continue` to see all errors
- Cache node_modules separately

**For Local Development:**
- Keep local cache enabled
- Don't force rebuild unless needed
- Use filters to build only what changed
- Clear cache if issues arise

**For Large Monorepos:**
- Use granular outputs
- Implement input filters
- Monitor cache size regularly
- Consider cache size limits on remote cache
