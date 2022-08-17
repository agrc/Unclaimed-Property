conda create --name unclaimed python=3.9
activate unclaimed
python -m pip install -U pip
pip install -r requirements.txt
conda install -c esri arcpy