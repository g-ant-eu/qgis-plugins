ncols = 40
nrows = 50
xllcorner = 500000
yllcorner = 5100000
cellsize = 10
nodata = -9999
testFileName = f"test_{nrows}x{ncols}.asc"
novaluePosition = 10

with open(testFileName, "w") as f:
    f.write(f"ncols         {ncols}\n")
    f.write(f"nrows         {nrows}\n")
    f.write(f"xllcorner     {xllcorner}\n")
    f.write(f"yllcorner     {yllcorner}\n")
    f.write(f"cellsize      {cellsize}\n")
    f.write(f"NODATA_value  {nodata}\n")

    val = 1.0
    for i in range(nrows):
        for j in range(ncols):
            if i == novaluePosition and j == novaluePosition:
                f.write(f"{nodata} ")
            else:
                f.write(f"{val} ")
                val += 1.0
        f.write("\n")
print(f"Test file '{testFileName}' generated with dimensions {ncols}x{nrows}, NODATA value at position ({novaluePosition}, {novaluePosition}).")
