- Main changes:
- Bump ppx-bom version to latest version `3.3082.0`.
- Update topology engine statistics processor metric keys ([ppx PR](https://bitbucket.lab.dynatrace.org/projects/PFS/repos/ppx/pull-requests/4877/overview), [Slack discussion](https://dynatrace.slack.com/archives/C0ARWR5JSAD/p1789995622586649)).
  
  Adapt to breaking changes:
- Remove usages of deleted flag `pipeline.executor.ppx.davis-events.forward.new-format` (`DavisFdiRecordProducer.produceDavisEventRecord` dropped the "new format" parameter with [this ppx PR](https://bitbucket.lab.dynatrace.org/projects/PFS/repos/ppx/pull-requests/4835/overview)).