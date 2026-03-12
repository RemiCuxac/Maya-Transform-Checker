from PySide2 import QtWidgets, QtCore
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui
import maya.cmds as cmds
from collections import defaultdict


def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

long=False
avoidRightSide = True

# TODO: in case multiple objects has the same name, list them before and / or rename them.
# TODO: Checker les doublons, et avoir la possibilité d'outrepasser s'il y en a (et afficher le longname à la place du shortname)
# TODO: détecter offset entre controler et objet contraint
# TODO: détecter clés sur les groupes (pas plus de 2 clés)
# TODO: détecter s'il y a eu un freeze transform (via comparaison entre local attributes, parent, et origine du world)
# TODO: Détecter s'il y a des objets sont symétriques (en position, et en rotation)
# TODO: Contraintes et clés sur le même objet (clés vertes)
# TODO: Quelles sont les objets contraints par plusieurs controlers
# TODO: Quels bones n'ont aucune contrainte
# TODO: Pas de contraintes sur les controllers
# TODO: (difficile) vérifier si la hiérarchie (sans les shapes, donc sans les dag nodes) correspond bien aux index des objets. Il faut pouvoir détecter qu'un bone nommé "blabla_04" ou "blabla4" est bien enfant d'un 3 ou 03.
# TODO: Checker si les bones comportant le mot "end" et "root" influencent le skin
# TODO: Détecter s'il y a plusieurs modifiers skin sur le même objet
# TODO: Vérifier si on est en camelCase ou PascalCase ou SnakeCase (éviter par exemple d'avoir une majuscule après un underscore...)
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Tool)

        self.setWindowTitle('Maya Transforms Checker')
        self.resize(300, 300)
        self.qlw_data = QtWidgets.QTableWidget()
        self.setCentralWidget(self.qlw_data)

        self.skel = cmds.ls(type="joint", long=long)
        self.controls = [cmds.listRelatives(i, p=1, type="transform", fullPath=long)[0] for i in
                         cmds.ls(type="nurbsCurve", o=1, r=1, ni=1, long=long)]
        self.dict_data = defaultdict(list)

        self.statusbar = QtWidgets.QStatusBar()
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)

        self.store_dict()
        self.update_table()
        self.update_list()
        self.qlw_data.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        #self.qlw_data.resizeColumnsToContents()
        self.connect_buttons()
        self.fit_to_table()

    def connect_buttons(self):
        self.qlw_data.itemSelectionChanged.connect(self.select_obj)

    def select_obj(self):
        selection = self.qlw_data.selectedItems()
        # We only care about the items in the first column (Object names)
        # itemSelectionChanged fires for any cell, so we filter for column 0
        nodes = list(set([self.qlw_data.item(item.row(), 0).text() for item in selection]))
        if nodes:
            cmds.select(nodes)

    def fit_to_table(self):
        x = self.qlw_data.verticalHeader().size().width()
        for i in range(self.qlw_data.columnCount()):
            x += self.qlw_data.columnWidth(i)

        y = self.qlw_data.horizontalHeader().size().height()
        for i in range(self.qlw_data.rowCount()):
            y += self.qlw_data.rowHeight(i)

        self.resize(x + 20, y+25)

    def update_table(self):
        self.qlw_data.setColumnCount(5)
        self.qlw_data.setHorizontalHeaderLabels(("Objects", "Translations", "Rotations", "Scale", "JointOrients"))
        self.qlw_data.setShowGrid(True)
        self.qlw_data.verticalHeader().setVisible(True)
        self.qlw_data.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.qlw_data.horizontalHeader().setDefaultSectionSize(100)
        self.qlw_data.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.qlw_data.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    def store_dict(self):
        self.check_trs(self.skel, self.dict_data, pAvoidRightSide=avoidRightSide)
        self.check_trs(self.controls, self.dict_data)

    def update_list(self):
        n = self.qlw_data.rowCount()
        self.qlw_data.setRowCount(n + len(self.dict_data))
        for i, (key, value) in enumerate(self.dict_data.items()):
            # bone name :
            itemBone = QtWidgets.QTableWidgetItem()
            self.qlw_data.setItem(i, 0, itemBone)
            itemBone.setText(key)
            for column, axis in enumerate(["Translate", "Rotate", "Scale", "JointOrient"]):
                if axis in value:
                    item = QtWidgets.QTableWidgetItem()
                    self.qlw_data.setItem(i, column+1, item)
                    item.setText("Wrong")

    @staticmethod
    def check_trs(pList, pDict, pTranslate: bool = True, pRotate: bool = True, pScale: bool = True,
                  pJointOrient: bool = True, pAvoidTranslateX=False, pAvoidRightSide=False) -> dict:
        excludeListParent = ["hand", "hips", "pelvis", "meta"]
        excludeListObj = ["meta", "constraint", "clav", "eye", "jaw", "pelvis", "hips"]
        for obj in pList:
            objParent = cmds.listRelatives(obj, parent=True, fullPath=long)
            objParent = objParent[0] if objParent is not None else ""
            if pAvoidRightSide:
                excludeListObj.append("right")
            checkParentChain = [True for name in excludeListParent if name in objParent.lower()]
            checkFistChain = [True for name in excludeListObj if name in obj.lower()]
            if (not any(checkParentChain)) and (not any(checkFistChain)):
                # for Translate, Rotate, Scale :
                for trs in ["Translate", "Rotate", "Scale"]:
                    if (pTranslate and trs == "Translate") or (pRotate and trs == "Rotate") or (pScale and trs == "Scale"):
                        for axis in ["X", "Y", "Z"]:
                            if (trs =="Translate" and axis !="X") or trs !="Translate":  # avoid Translate X
                                if trs == "Scale":
                                    min, max = 0.99, 1.01
                                else:
                                    min, max = -0.01, 0.01
                                if not min < cmds.getAttr(f"{obj}.{trs.lower()}{axis}") < max:
                                    if not pDict[obj] or not trs in pDict[obj]:
                                        pDict[obj].append(trs)
                # for jointOrients
                if pJointOrient:
                    if cmds.objectType(obj, isType="joint"):
                        if sum([-0.01 < cmds.getAttr(f"{obj}.jointOrient{axis}") < 0.01 for axis in ["X", "Y", "Z"]]) <= 1:
                            if not pDict[obj] or not "JointOrient" in pDict[obj]:
                                pDict[obj].append("JointOrient")
        return pDict


if __name__ == "__main__":
    try:
        mayaTrsChecker.deleteLater()
    except:
        pass
    mayaTrsChecker = MainWindow(parent=maya_main_window())
    mayaTrsChecker.show()
