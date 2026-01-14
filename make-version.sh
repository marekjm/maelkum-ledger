#!/bin/sh

set -e

VERSION=$(cat $(git rev-parse --show-toplevel)/VERSION)
SUFFIX=
TAG="v${VERSION}"

suffix_path=$(git rev-parse --show-toplevel)/VERSION-SUFFIX
if [ -f ${suffix_path} ]; then
    SUFFIX=$(cat ${suffix_path})
fi


# We have to explicitly delete whitespace since BSD version of wc(1) emits some
# in front of the count.
COMMITS_SINCE=$(git log --oneline ${TAG}..HEAD | wc -l | tr -d ' ')

GIT_HEAD=$(git rev-parse HEAD)
GIT_DIRTY=''
if [ $(git ls-files -m | wc -l) -ne 0 ]; then
    GIT_DIRTY='+dirty'
fi

# Why is 32 the magic number used for the size of the hash?
#
# Because the greatest number of commits in a year, in the decade between 2014
# and 2024, has been 90895. This value, divided by the number of releases per
# year, averaging 6, gives us 15149--which is our target number of commits per
# release.
#
# See https://www.phoronix.com/news/2024-Linux-Git-Stats for the source of this
# data.
#
# I want the version string to be as close to 68 characters as possible, while
# not exceeding that value. Given that the most recent Linux release (at the
# time of writing) is 6.18 we arrive at the following layout for the version
# string:
#
#  - four characters for the base release eg, 6.18
#  - five characters for the patch count eg, 15149
#  - one character for the dot (.) between the base release and the patch count
#  - one character for the hyphen (-) between the version and the fingerprint
#  - fifty-seven (57) characters for the fingerprint
#
# Instead of using some arbitrary way of signalling that a hash is used like
# prefixing it with "h" or "fp" (for FingerPrint), or just serving the digest
# raw, a https://multiformats.io/multihash/ is used.
#
# Encoding the hash ID in the above format will take two characters, and
# encoding the size of the digest another two (since we are working with
# relatively small numbers).
#
# This leaves us with only 53 characters for the digest; and since each hex
# digit represents four bits, the size of the hash can be at most 26 bytes.
#
#
# Now, why make 68 the target version string length?
#
# Because the suggested max line width for prose part of commit messages in Git
# is "no more than 70-75 characters" and the average of these numbers is 72. See
# https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/process/submitting-patches.rst?h=v6.18&id=7d0a66e4bb9081d75c82ec4957c50034cb0ea449#n696
# and https://github.com/torvalds/linux/pull/17#issuecomment-5661185 for
# references and rationale.
#
# 72 is the result of taking the standard terminal line width of 80 characters
# and reserving some space for indentation, while taking note of the default
# 4-character wide indentation of commit messages performed by git-log(1).
#
# 68 is simply an "extension" of the above: allowing the number to be used in
# Git commit messages with some indentation and without line-breaking when
# displayed in a terminal using the standard line width.
#
# For example, when reporting a bug one could say in the commit message:
#
#   The build with ID
#       6.18.21378-1e1a82b68fe204c1b430508b65848686cb87fe507d8e0d1bbf594db9
#   broke XYZ and caused ABC to happen.
#
# while staying within the 72-character limit.
#
#
# Having said all that, I do not expect the "fingerprint" style to be used much
# outside of development. The only advantage it has over the "full" style (ie,
# simple version, commit ID, and an optional dirty flag) is allowing a user to
# differentiate two dirty programs based on the same commit that are dirty in a
# SLIGHTLY DIFFERENT way.
#
# Will anyone ever actually use it? Hell if I know. I do.
HASH_SIZE=26

# See https://github.com/multiformats/multicodec/blob/master/table.csv for
# values identifying different hashes.
HASH_TYPE='1e'  # BLAKE3

FINGERPRINT=$(git ls-files --cached |
    sort |
    xargs -n 1 cat |
    b3sum -l ${HASH_SIZE} |
    cut -d' ' -f1 |
    cat)
FINGERPRINT_PREFIX="${HASH_TYPE}$(printf '%x' ${HASH_SIZE})"

MODE=${1:-default}

if test "${MODE}" = '--help'
then
    echo "usage: $0 ( <style> | auto )"
    echo "  <style> must be one of:"
    cat "$0" | grep -P '^\s+[a-z|]+\)  #' | sed 's/)  #/\t/'
    echo "  or 'auto' to signal automatic selection of the most appropriate mode"
    exit 0
fi

if [ "${MODE}" = 'auto' ]; then
    if [ -n "${GIT_DIRTY}" ]; then
        MODE=fingerprint
    else
        MODE=default
    fi
fi

case ${MODE} in
    short|default)  # just the version
        echo "${VERSION}.${COMMITS_SINCE}${SUFFIX}"
        ;;
    full)  # version tagged with the HEAD commit
        echo "${VERSION}.${COMMITS_SINCE}${SUFFIX}-g${GIT_HEAD}${GIT_DIRTY}"
        ;;
    base|release)  # base release (with 0 as patch segment)
        echo "${VERSION}.0${SUFFIX}"
        ;;
    fingerprint|fp)  # fingerprint of the code
        echo "${VERSION}.${COMMITS_SINCE}${SUFFIX}-${FINGERPRINT_PREFIX}${FINGERPRINT}"
        ;;
    *)
        exit 1
        ;;
esac
