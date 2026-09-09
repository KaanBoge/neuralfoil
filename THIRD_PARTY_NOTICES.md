# Third party notices

This is a separate project maintained by Kaan Boge, not upstream NeuralFoil. Attribution does not imply upstream endorsement or a blanket license for repository contents.

## NeuralFoil and AeroSandbox

The numerical workflow uses [NeuralFoil](https://github.com/peterdsharpe/NeuralFoil) 0.3.3 and [AeroSandbox](https://github.com/peterdsharpe/AeroSandbox) 4.2.10, developed by Peter Sharpe and contributors. Their installed release records contain the MIT license:

- NeuralFoil: Copyright (c) 2023-2023 Peter Sharpe.
- AeroSandbox: Copyright (c) 2019-2023 Peter Sharpe.

The existing browser's network assets and port derive from upstream work. Preserve applicable notices when distributing copies or substantial portions. The following upstream permission text is not a license grant for this project's own code or data.

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Other dependencies and inputs

The tracked legacy `study/README.md` contains scoped historical data/tool/document declarations. Its stated CC-BY 4.0 scope does not independently verify underlying data rights. The current original-code MIT grant is in the root [LICENSE](LICENSE); [LICENSING.md](LICENSING.md) explains its scope. Neither grant relicenses third-party material.

XFOIL is NeuralFoil's numerical teacher, not a newly authored experimental dataset or solver from this project. Imported libraries and browser dependencies retain their own licenses; an import does not authorize redistribution of an entire installation. Environments and caches are not part of the new source archive.

SoarTech/UIUC measurements and recovered geometry have separate acquisition histories and permissions. Software licenses do not confer dataset rights. See [the data guide](docs/DATA.md). Preserve original attribution and consult file-specific terms before onward distribution.
