# tectonic (brew install tectonic) runs BibTeX itself and fetches packages on first use
pdf: main.pdf

main.pdf: main.tex refs.bib $(wildcard tables/*.tex) $(wildcard figures/*.pdf)
	tectonic --keep-logs main.tex

tables:
	cd .. && python research/report.py

clean:
	rm -f main.pdf main.aux main.bbl main.blg main.log

.PHONY: pdf tables clean
