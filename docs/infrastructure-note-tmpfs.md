# Test Infrastructure Note

**Date:** 2026-09-18  
**Issue:** `/tmp` is mounted as tmpfs (1.9GB total) on this workstation.

**Problem:** Previous testing left three 635MB honcho image archives in `/tmp`, consuming 100% of tmpfs space. This caused pytest failures with `OSError: [Errno 28] No space left on device`.

**Resolution:** Deleted stale archives:
```bash
rm /tmp/honcho-latest*.tar
```

**Recommendation for future:**
- Use `/home/sysop/tmp/` or a dedicated directory for large file operations
- Add test cleanup step to delete temporary archives after use
- Consider increasing tmpfs size if needed for container workflows

**Current tmpfs status:**
- Size: 1.9GB
- Used: ~4KB (after cleanup)
- Available: ~1.9GB
