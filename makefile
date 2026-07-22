# name
name = orga_units_xml

# docdir = ~/numlims.github.io/tram  # e.g. ~/mydoc.github.io/myprogram
# docmake = ~/numlims.github.io  # e.g. ~/mydoc.github.io

# get the version from github tag
# sort by version; get the last line; delete the v from the version tag cause python build seems to strip it as well
# version = $(shell git tag | sort -V | tail -1 | tr -d v)
version = 0.0.3
all:
	

.PHONY: build install test doc doc-publish publish publish-update

build:
	make
	python3 -m build --no-isolation

install:
	make build
	pip install "./dist/${name}-${version}-py3-none-any.whl" --no-deps --force-reinstall

test:
	make install
	pytest -s

doc:
	make
	pdoc "./${name}" -o html

doc-publish:
	make doc
	mkdir -p ${docdir}
	cp -r html/* ${docdir}
	cd ${docmake} && make publish

publish:
	make build
	# move the version tag to the most recent commit
	git tag -f "v${version}"
	# delete tag on remote
	git push origin ":refs/tags/v${version}" 
	git push --tags   # push the local tags
	gh release create "v${version}" "./dist/${name}-${version}-py3-none-any.whl"
	make doc-publish

publish-update: # if an asset was already uploaded, delete it before uploading again
	make build
	# does the tag updating also update the source code at the resource?
	# move the version tag to the most recent commit
	git tag -f "v${version}"
	# delete tag on remote
	git push origin ":refs/tags/v${version}" 
	# re-push the tag to the remote
	git push --tags
	gh release delete-asset "v${version}" "${name}-${version}-py3-none-any.whl" -y
	gh release upload "v${version}" "./dist/${name}-${version}-py3-none-any.whl"
	# apparently the tag change rolled the release back to draft, set it to publish again
	gh release edit "v${version}" --draft=false
	make doc-publish
