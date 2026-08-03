# Frozen evaluation corpus

`frozen/manifest.json` is the authoritative inventory snapshot. It records each direct source URL,
the verified post text, the local media path, the source-media URL, a SHA-256 digest, and a
perceptual hash. Loading the corpus verifies the manifest hash and every local media digest before
evaluation.

The post text and media are third-party evaluation data. They are not relicensed under this
repository's MIT license. Rights remain with their original authors and publishers. Source URLs are
kept in the manifest for provenance.
