package eagrn;

import eagrn.cutoffcriteria.CutOffCriteriaOnlyConf;

import java.io.*;
import java.util.*;

public class SingleNetworkRunner {
    public static void main(String[] args){
        /** Declare the main execution variables */
        CutOffCriteriaOnlyConf cutOffCriteriaOnlyConf;

        /** Read input parameters */
        String listOfLinksStrFile;
        String geneNamesStrFile;
        String outputStrFile;
        String strCutOffCriteria;
        double cutOffValue;

        if (args.length > 2) {
            listOfLinksStrFile = args[0];
            geneNamesStrFile = args[1];
            outputStrFile = args[2];
            if (args.length == 5) {
                strCutOffCriteria = args[3];
                cutOffValue = Double.parseDouble(args[4]);
            } else {
                strCutOffCriteria = "MinConfidence";
                cutOffValue = 0.1;
            }
        } else {
            throw new RuntimeException("The list of confidence values, the list of gene names and the path to the output file are three required parameters.");
        }

        /** Establish the cut-off criteria */
        cutOffCriteriaOnlyConf = (CutOffCriteriaOnlyConf) StaticUtils.getCutOffCriteriaFromString(strCutOffCriteria, cutOffValue, true);

        /** Extracting gene names */
        ArrayList<String> geneNames = StaticUtils.getGeneNames(geneNamesStrFile);

        /** Extract the list of links */
        Map<String, Double> map = StaticUtils.getMapWithLinks(new File(listOfLinksStrFile));

        /** Calculate the binary matrix according to the selected criteria */
        int[][] binaryNetwork = cutOffCriteriaOnlyConf.getNetwork(map, geneNames);

        /** Write the resulting binary matrix to an output csv file */
        StaticUtils.writeBinaryNetwork(outputStrFile, binaryNetwork, geneNames);
    }
}
