# Tasks: remove-cluster-minio

- [x] 1. Sanity vooraf: wordsworth gezond op SeaweedFS (health + search + objectaantal)
- [x] 2. Cluster: Application `minio` verwijderen (cascade via finalizer), namespace `minio` weg
- [x] 3. Git: minio.yaml + cluster-config/infra/minio/ verwijderen, CHANGELOG-regel
- [x] 4. Verificatie: wordsworth nog gezond; geen minio-resources/refs meer
- [x] 5. Change archiveren

Uitvoering 2026-08-27: workloads/PVC/namespace verwijderd, Git opgeschoond, wordsworth
gezond op SeaweedFS (415 objecten). REST: het Application-object minio hangt in
deletie op zijn finalizer (controller verwerkt m niet, ook na restart); resources
zijn aantoonbaar weg. Handmatige afronding (classifier blokkeerde de patch):
kubectl -n argocd patch application minio --type merge -p '{"metadata":{"finalizers":null}}'
