-
- Ingested spans per tenant:
  ```
  timeseries { sum = sum(remote_dsfm.server.spans.received.count, scalar:true),by: { dt.tenant.uuid }}
  | sort sum desc
  | limit 100
  ```
-
- Logs of ppx with ingestdomaintype dedup:
- ```
  fetch logs
  | filter k8s.cluster.name == "mawo-loadtest-12933-90v5e5aq" and k8s.namespace.name == "deus" and (k8s.workload.name == "ppx-service" or in(k8s.pod.name, lookup([
  smartscapeEdges "is_part_of"
  | filter target_id == toSmartscapeId("K8S_DEPLOYMENT-FB3FDB45114B335B") and source_type == "K8S_POD"
  | fields k8s.pod.name = getNodeName(source_id)
  ], sourceField:k8s.pod.name, lookupField:k8s.pod.name)[k8s.pod.name]))
  | filter status == "ERROR" OR status == "WARN"
  | filter content ~ "IngestDomainType{"
  | parse content , """LD "IngestDomainType{" DATA:ingestdomaintype "}" LD"""
  | dedup ingestdomaintype
  | fieldsAdd type
  - | sort timestamp desc
  ```
-