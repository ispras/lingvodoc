This instruction is related to Min.io object storage usage and configuration
to use it inside Lingvodoc.

To use minio in lingvodoc first of all you should make the following:

1. Enter maintenance mode
```
mc config host add minio https://minio.example.com
Enter Access Key:
Enter Secret Key:
```

2. Create users.

3. Create needed subpaths (look the next item for description) and apply
retention policies (self-descriptive in file retention.json).

3. Import policies. Policies in these json files mean the following:
  1. Lingvodoc admin. May do anything including new path creation in bucket.
  2. Lingvodoc read-only policy (default for users). End-users do not have
  account in minio instance thus should get access without prompt. __We may want
  to disable this policy in future if we will get multitenancy access issues__
  and may want to use lingvodoc as proxy for objects.
  3. Lingvodoc prod instances role. Each instance has its own subpath in bucket
  with r/w access. Maintainers for instances must be careful with access tokens.
  4. Lingvodoc staging/dev instances role. They share one subpath.

4. Import retention policies for subpaths. Proposed policy is 4 days for temp
objects in prod; 1 day for staging/dev.

If you are going to maintain lingvodoc instance you should either contact with
us to use our minio, either get your own (or use local storage with cron-based
  retention mechanics).

To apply policies you can use configure_minio.sh script (but you should revise
  it before usage).
