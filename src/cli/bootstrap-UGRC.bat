"C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\conda" create --name unclaimed python=3.7
"C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\activate" unclaimed
python -m pip install -U pip
pip install -r requirements.txt
"C:\Program Files\ArcGIS\Pro\bin\Python\Scripts\conda" install -c esri arcpy=2.7
