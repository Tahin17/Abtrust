# BracU Thesis - Chapters 1 to 4

This Overleaf-ready project follows the supplied Brac University thesis template.

## Compile on Overleaf
- Compiler: **pdfLaTeX**
- Bibliography processor: **Biber**
- Main file: `main.tex`

## Citation / bibliography format
The project uses the same bibliography configuration as the supplied thesis template:

```latex
\usepackage[backend=biber,style=ieee,sorting=ynt]{biblatex}
\addbibresource{bibliography/references.bib}
```

All Chapters 1-4 use the single combined `bibliography/references.bib` file. In-text citations are generated numerically with `\cite{...}`, and one combined Bibliography is printed at the end of Chapter 4.

Because LaTeX/Biber generates citation numbers automatically, numbers may differ from manually numbered citations in the Word draft after sources from multiple chapters are merged. The generated in-text number and bibliography entry remain linked automatically.

## Declaration signatures
The declaration page contains signatures for:
- MD. Nafiul Haque Nafee - 23101244
- Tausif Ishrak - 23101007
- Kaspia Khan Onti - 23101145
- Saleha Sattar Oishy - 23101045

The Tausif Ishrak and Kaspia Khan Onti signatures were recovered from the rendered declaration page of the updated Word document because those two signatures were stored there as Word drawing/ink objects rather than ordinary embedded image files.
