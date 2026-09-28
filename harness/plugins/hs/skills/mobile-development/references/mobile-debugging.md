# Mobile Debugging Strategies

Debugging techniques, tools, best practices for mobile dev (2024-2025).

## Mobile Debugging Mindset

### Unique Mobile Challenges

1. **Device Diversity** - Thousands of device/OS combinations
2. **Resource Constraints** - Limited CPU, memory, battery
3. **Network Variability** - From WiFi to 2G, offline scenarios
4. **Platform Differences** - iOS vs Android behavior
5. **Real Device Testing** - Simulators don't show real performance
6. **Limited Debugging Access** - Can't SSH into production devices

### Debugging Philosophy

**Golden Rules:**
1. **Test on real devices** - Simulators lie about performance
2. **Reproduce consistently** - Intermittent bugs need reproducible steps
3. **Check the obvious first** - Network, permissions, resources
4. **Isolate the platform** - Is it iOS-specific, Android-specific, or both?
5. **Monitor resources** - CPU, memory, battery, network
6. **Read the logs** - Device logs contain critical clues


---

Continued in [mobile-debugging-cont.md](mobile-debugging-cont.md)
