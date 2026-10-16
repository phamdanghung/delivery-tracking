# Recovery runbook — local verification, production gates riêng

## Ranh giới

Canonical: `fleet-delivery-dev`. Legacy `fleet-delivery` và runtime/volume cũ: PRESERVED; không reset/prune/xóa/migrate. Không coi dữ liệu development là production. Các lệnh dưới không phải phê duyệt production.

## Backup local có maintenance window

Chạy bằng Python trong `apps/api/.venv` từ root repo:

```text
python scripts/backup_restore.py backup --bundle artifacts/backups/manual-YYYYMMDD-HHMMSS
```

- Output phải là thư mục mới dưới `artifacts/backups`, ignored; owner-only ACL trên Windows hoặc mode 0700 trên Unix. Không commit/chia sẻ dump, credentials, GPS hoặc ảnh.
- Script chỉ nhận canonical hoặc runtime recovery test UUID được giới hạn; từ chối legacy/unrelated source. Cần local `.env` đáng tin cậy và Docker Engine hoạt động.
- Dừng API writes, Traccar và MinIO; dùng pg_dump custom format và cold archive MinIO/Traccar H2. Không sao chép H2/MinIO đang ghi. Lưu fingerprint dữ liệu/tables, migration head, image IDs, file hashes và manifest hoàn tất.
- Trong maintenance window, dừng cả writer ngoài các container này (SQL console, script hoặc API khác nếu có). Adapter không khóa writer bên ngoài; fingerprint khác sau restore phải FAIL, không được xem backup là nhất quán chỉ vì pg_dump thành công.
- Restart đúng các service đã dừng trong finally. Kiểm tra `restart_failures` và health sau backup; `docker start` thành công không tự chứng minh service đã ready.
- Archive MinIO giữ backend metadata/version IDs, không upload lại bằng S3 PUT rồi giả định version ID cũ còn đúng. Audit và POD/receipt metadata phải khớp object version được restore.
- Không tự xóa backup/ảnh theo tuổi; retention/RPO/RTO đang chờ chủ dự án chốt. Không mã hóa/offsite/PITR bằng giải pháp tự chọn rồi tuyên bố production đạt.

## Restore drill không ghi đè

```text
python scripts/backup_restore.py restore-check --bundle artifacts/backups/manual-YYYYMMDD-HHMMSS
```

Chỉ dùng bundle do chính hệ thống local tạo và tin cậy. Checksum bảo vệ tính toàn vẹn, không chứng minh nguồn backup đáng tin cậy; pg_restore có thể chạy SQL trong dump. Script kiểm tra hash, completeness, archive paths/types và image IDs trước khi tạo tài nguyên.

Restore vào project `fleet-delivery-restore-<uuid>`, volumes/network mới, không publish ports. So fingerprint mọi bảng, PostGIS/head; ảnh private/versioned, original version IDs, SHA256/signed GET; Traccar khởi động từ H2 restored. Chỉ cleanup container/volume/network có tên và ownership label đúng của lượt drill, không prune.

Theo dõi report/journal trong bundle. Nếu drill bị ngắt/crash, không xóa theo prefix chung; đối chiếu exact UUID + ownership label trước khi cleanup tài nguyên còn lại. Không dùng lỗi drill làm lý do reset canonical.

## Bài kiểm chứng tự động local/CI

```text
python scripts/verify_recovery.py
```

Tạo source test `fleet-delivery-backup-test-<uuid>` riêng với PostgreSQL/MinIO/Traccar/API, ports loopback ngẫu nhiên. Tạo POD/GPS canary chỉ trong môi trường test; backup/restore/so dữ liệu thật, sau đó cleanup đúng source/target có ownership label. Không stop, seed hoặc thay canonical. Bằng chứng tổng hợp: `artifacts/m8-recovery-result.json`; diagnostics private dưới `artifacts/recovery` và backup bundles được giữ lại.

## Sau can thiệp canonical

```text
docker compose -p fleet-delivery-dev ps
python scripts/verify_stack.py
python scripts/verify_osrm.py
```

Không dùng test stack thay canonical. Không tạo dữ liệu nghiệp vụ giả vào canonical để làm health xanh. Chưa có bằng chứng restore thì ghi CHƯA XÁC MINH.

## Production chưa được phê duyệt

Cần chốt target/maintenance allowance/RPO/RTO/retention; credentials tương ứng snapshot được giữ trong vault riêng; backup encrypted/offsite/immutable; DB daily scheduler và PITR nếu provider hỗ trợ; image/digest availability; restore rehearsal trên staging tương ứng production, gồm ảnh và GPS history; log retention/access/on-call. Cold local H2/volume drill không tự đáp ứng khả năng sẵn sàng hoặc SLA production.

Nguồn: [PostgreSQL pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html), [Docker volumes backup/restore](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes), Technical Pack 07. Không triển khai phục hồi ghi đè production bằng adapter local này.
