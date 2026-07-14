function DEBUG_PARAMS_CACHE_VISIBLE() {
  const k = "IRV_PARAMS_SNAPSHOT_V1";
  return [
    !!CacheService.getScriptCache().get(k),
    !!PropertiesService.getScriptProperties().getProperty(k)
  ];
}
